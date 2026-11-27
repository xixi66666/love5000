package com.example.website.integration.local;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/**
 * 本机服务（Strata 9999、AIMedia 操作台 8190、H3 ComfyUI 8189）的 HTTP 客户端。
 *
 * <p>属于 integration/local 的传输层：只对 {@code 127.0.0.1} 发起请求，主机名写死，
 * 不接受外部传入的 URL 或地址。连接超时固定 2000 毫秒，读取超时由调用方决定
 * （GET 固定 4000 毫秒，POST 使用启动等待时长）；不跟随重定向，避免被引导到其它地址。</p>
 *
 * <p>失败语义分两档：{@link #get} 吞掉所有异常返回 {@code null}，供状态探测使用，
 * 调用方只需判断在线与否；{@link #post} 把失败转换成 {@link LocalServiceException}，
 * 由控制器映射为 409 或 503。所有对外提示都是固定中文文案，不带上游响应体，
 * 也不把本机路径写进响应。</p>
 */
@Component
public class LocalServiceClient {
    private final ObjectMapper mapper;

    public LocalServiceClient(ObjectMapper mapper) {
        this.mapper = mapper;
    }

    /**
     * 读取本机服务的 JSON 接口，失败即视为离线。
     *
     * <p>供状态与健康探测使用：超时、连接失败、非 2xx、响应不是合法 JSON 都返回
     * {@code null}，调用方不需要区分错误类型。</p>
     *
     * @param port 本机端口
     * @param path 以斜杠开头的请求路径
     * @return 解析后的 JSON；任何失败返回 {@code null}
     */
    public JsonNode get(int port, String path) {
        try {
            return exchange(port, path, null, 4000);
        } catch (LocalServiceException exception) {
            return null;
        }
    }

    /**
     * 向本机服务提交 JSON 操作请求。
     *
     * <p>请求体按 UTF-8 写出，并附带固定的 {@code X-AIMedia-Client: studio} 客户端标识，
     * 本机 AIMedia 侧按该标识区分调用方。</p>
     *
     * @param port      本机端口
     * @param path      以斜杠开头的请求路径
     * @param body      JSON 请求体
     * @param timeoutMs 读取超时，单位毫秒；加载或卸载模型等长耗时操作应传入启动等待时长
     * @return 解析后的 JSON 响应；空响应体视为失败
     * @throws LocalServiceException 端口或路径非法、服务忙（409）、非 2xx、超时或网络失败时抛出
     */
    public JsonNode post(int port, String path, String body, int timeoutMs) {
        return exchange(port, path, body, timeoutMs);
    }

    /**
     * 执行一次本机 HTTP 交换并统一错误映射。
     *
     * <p>先校验端口范围与路径前缀，避免被拼装成任意地址；非 2xx 响应中只把 409 透传为
     * 「服务忙」，其余一律折叠为 503，防止把上游状态码与错误体当作对外契约。
     * {@code body} 为 {@code null} 时走 GET，否则走 POST。</p>
     *
     * @param port      目标端口，必须在 1 到 65535 之间
     * @param path      请求路径，必须以斜杠开头
     * @param body      JSON 请求体；{@code null} 表示 GET
     * @param timeoutMs 读取超时，单位毫秒
     * @return 解析后的 JSON 响应
     * @throws LocalServiceException 参数非法、HTTP 失败或网络异常时抛出
     */
    private JsonNode exchange(int port, String path, String body, int timeoutMs) {
        if (port < 1 || port > 65535 || !path.startsWith("/")) {
            throw new LocalServiceException(503, "本机服务配置无效");
        }
        HttpURLConnection connection = null;
        try {
            connection = (HttpURLConnection) new URL("http://127.0.0.1:" + port + path).openConnection();
            connection.setConnectTimeout(2000);
            connection.setReadTimeout(timeoutMs);
            connection.setInstanceFollowRedirects(false);
            connection.setUseCaches(false);
            if (body != null) {
                connection.setRequestMethod("POST");
                connection.setRequestProperty("Content-Type", "application/json");
                connection.setRequestProperty("X-AIMedia-Client", "studio");
                connection.setDoOutput(true);
                try (java.io.OutputStream output = connection.getOutputStream()) {
                    output.write(body.getBytes(StandardCharsets.UTF_8));
                }
            }
            int status = connection.getResponseCode();
            if (status < 200 || status >= 300) {
                throw new LocalServiceException(status == 409 ? 409 : 503,
                        status == 409 ? "服务正在处理请求，请完成或停止当前任务后重试" : "本机服务操作失败，请检查该服务日志");
            }
            try (InputStream input = connection.getInputStream()) {
                JsonNode value = mapper.readTree(input);
                if (value == null) throw new IOException("Empty response");
                return value;
            }
        } catch (IOException exception) {
            throw new LocalServiceException(503, "本机服务未就绪或操作超时，请检查服务状态和日志");
        } finally {
            if (connection != null) connection.disconnect();
        }
    }
}
