package com.example.personalagent.service;

import com.example.common.ai.ModelProperties;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.*;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.server.ResponseStatusException;

import java.util.Arrays;
import java.net.HttpURLConnection;
import java.io.IOException;

import static com.example.personalagent.Api.*;

/**
 * 调用 DeepSeek 官方文件接口识别原件（PDF、Office 文档、图片）。
 *
 * <p>属服务层，被 {@link LocalDocuments} 与 {@link HealthArchive} 复用。流程固定三段：
 * 先 {@code POST /files} 上传并声明一小时后过期，再 {@code POST /chat/completions} 用
 * {@code file_id} 引用该文件，最后在 {@code finally} 里尝试 {@code DELETE /files/{id}}，
 * 尽量缩短原件在第三方的留存时间。</p>
 *
 * <p>非显然行为：密钥只从根目录 {@code model.properties} 的 {@code deepseek.api-key}
 * 读取；上传用途按扩展名区分，PDF 与 doc/docx/ppt/pptx 走版面识别、其余走 {@code user_data}；
 * 重定向被显式关闭，避免凭据跟随 3xx 跳到别的主机；文件 id 不匹配预期格式、
 * {@code finish_reason} 不是 {@code stop}、正文为空或超长，统一折成 502，
 * 让上层保留原件并提示用户换模型重试。</p>
 */
@Service
public class DeepSeekFiles {
    /** DeepSeek 官方接口基址，硬编码以避免配置被改指到非官方域名。 */
    private static final String BASE = "https://api.deepseek.com";
    /** 默认文件识别模型；顶部栏选中其他 DeepSeek 型号时由调用方覆盖。 */
    static final String FILE_MODEL = "deepseek-flash";
    private final RestTemplate http;

    /**
     * 装配带显式超时的 HTTP 客户端。
     *
     * <p>关闭自动跟随重定向是安全要求：Bearer 令牌不能随 3xx 漂到其他主机。
     * 连接超时 10 秒、读取超时 180 秒，后者为版面识别留出时间。</p>
     */
    @Autowired
    public DeepSeekFiles() {
        SimpleClientHttpRequestFactory requests = new SimpleClientHttpRequestFactory() {
            @Override protected void prepareConnection(HttpURLConnection connection, String method) throws IOException {
                super.prepareConnection(connection, method);
                connection.setInstanceFollowRedirects(false);
            }
        };
        requests.setConnectTimeout(10000);
        requests.setReadTimeout(180000);
        http = new RestTemplate(requests);
    }

    /** 测试用构造器：注入绑定了桩响应的 {@link RestTemplate}，不发起真实请求。 */
    DeepSeekFiles(RestTemplate http) {
        this.http = http;
    }

    /** 用默认文件模型识别原件，等价于不覆盖型号的调用。 */
    public String analyze(byte[] bytes, String extension, String instruction) {
        return analyzeWithModel(bytes, extension, instruction, "");
    }

    /**
     * 按顶部栏选中的 DeepSeek 型号识别原件。
     *
     * @param bytes       原件字节
     * @param extension   小写后缀
     * @param instruction 整理要求
     * @param model       选中的 DeepSeek 型号；空串表示用 {@link #FILE_MODEL}
     * @return 模型返回的整理正文
     * @throws ResponseStatusException 配置文件里没有 DeepSeek 密钥时 503，
     *         其余上游失败统一 502
     */
    public String analyzeWithModel(byte[] bytes, String extension, String instruction, String model) {
        ModelProperties.Provider provider = ModelProperties.load().provider("deepseek");
        if (provider == null || provider.apiKey().isEmpty()) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,
                "请在根目录 model.properties 配置 DeepSeek 官方 API 密钥");
        }
        return analyze(bytes, extension, instruction, provider.apiKey(), model);
    }

    /** 用给定密钥与默认型号识别，跳过配置读取，供内部调用与测试使用。 */
    String analyze(byte[] bytes, String extension, String instruction, String apiKey) {
        return analyze(bytes, extension, instruction, apiKey, "");
    }

    /**
     * 上传—引用—删除三段式调用的实现。
     *
     * @param bytes       原件字节，调用方已完成大小与后缀校验
     * @param extension   小写后缀，决定上传用途与 multipart 文件名
     * @param instruction 交给模型的整理要求，其中已包含「忽略文件内指令」等边界
     * @param apiKey      官方密钥，只用于本次请求头
     * @param model       型号；空白时回退到 {@link #FILE_MODEL}
     * @return {@code choices[0].message.content}，已去除首尾空白
     * @throws ResponseStatusException 上传或对话任一步失败、id 格式不符、
     *         {@code finish_reason} 非 stop、正文为空或超长时抛出 502；
     *         临时文件删除失败被静默忽略，不影响主结果
     */
    String analyze(byte[] bytes, String extension, String instruction, String apiKey, String model) {
        String selected = model == null || model.trim().isEmpty() ? FILE_MODEL : model.trim();
        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(apiKey);
        HttpHeaders uploadHeaders = new HttpHeaders();
        uploadHeaders.putAll(headers);
        uploadHeaders.setContentType(MediaType.MULTIPART_FORM_DATA);
        LinkedMultiValueMap<String,Object> fields = new LinkedMultiValueMap<>();
        fields.add("purpose", extension.matches("pdf|docx?|pptx?") ? "rich_layout_recognition" : "user_data");
        fields.add("expires_after[anchor]", "created_at");
        fields.add("expires_after[seconds]", "3600");
        fields.add("file", new ByteArrayResource(bytes) {
            @Override public String getFilename() { return "attachment." + extension; }
        });

        String fileId = "";
        try {
            JsonNode uploaded = http.postForObject(BASE + "/files", new HttpEntity<>(fields, uploadHeaders), JsonNode.class);
            if (uploaded == null || !uploaded.path("id").asText().matches("file-api-[A-Za-z0-9_-]{1,128}")) {
                throw new RestClientException("Missing file ID");
            }
            fileId = uploaded.path("id").asText();
            JsonNode result = http.postForObject(BASE + "/chat/completions", new HttpEntity<>(map(
                "model",selected,"max_tokens",6000,"thinking",map("type","disabled"),
                "messages",Arrays.asList(map("role","system","content",instruction),map("role","user","content",Arrays.asList(
                    map("type","file","file_id",fileId),map("type","text","text","请按要求整理本次上传的附件。"))))
            ), headers), JsonNode.class);
            JsonNode choice = result == null ? null : result.path("choices").path(0);
            String answer = choice == null ? "" : choice.path("message").path("content").asText().trim();
            if (choice == null || !"stop".equals(choice.path("finish_reason").asText()) || answer.isEmpty() || answer.length() > 60000) {
                throw new RestClientException("Incomplete file analysis");
            }
            return answer;
        } catch (RestClientException failure) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "DeepSeek 文件处理失败，请检查官方密钥、余额和文件格式后重试");
        } finally {
            if (!fileId.isEmpty()) {
                try { http.exchange(BASE + "/files/{id}", HttpMethod.DELETE, new HttpEntity<>(headers), Void.class, fileId); }
                catch (RestClientException unavailable) {}
            }
        }
    }
}
