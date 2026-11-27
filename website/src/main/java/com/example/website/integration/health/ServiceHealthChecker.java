package com.example.website.integration.health;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.io.InputStream;
import java.net.ConnectException;
import java.net.HttpURLConnection;
import java.net.SocketTimeoutException;
import java.net.URL;
import java.util.concurrent.TimeUnit;

/**
 * 单目标健康探测器。
 *
 * <p>属于 integration/health 的传输层，只做一件事：对给定地址发起一次 GET 并判定在线
 * 状态。判定标准是「HTTP 2xx 且响应体顶层存在布尔字段 {@code success=true}」，
 * 二者缺一即视为离线，这是八个独立服务与三个本机适配服务共同的健康约定。</p>
 *
 * <p>超时来自 {@link ServiceHealthProperties}，默认连接 2000 毫秒、读取 3000 毫秒，
 * 单个目标最坏约 5 秒；聚合器为每个目标各起一个线程，因此并行后整轮耗时仍在这个量级。
 * 所有网络异常（超时、连接拒绝、其它 IO 异常）都被转换成离线结果而不是抛出，
 * 调用方无需 try/catch。离线提示使用固定短码（如 {@code Timed out}、{@code HTTP 503}），
 * 不回传上游响应体，避免把服务内部信息带进页面。</p>
 *
 * <p>每次探测记录一行结构化日志，只含项目名、状态、状态码和耗时，不打印完整 URL，
 * 防止带查询串的地址进入日志。</p>
 */
@Component
public class ServiceHealthChecker {

    private static final Logger log = LoggerFactory.getLogger(ServiceHealthChecker.class);

    /**
     * 休眠抽象，便于测试注入空实现而跳过真实等待。
     */
    interface Sleeper {
        void sleep(long millis) throws InterruptedException;
    }

    private final ObjectMapper objectMapper;
    private final ServiceHealthProperties properties;
    private final Sleeper sleeper;

    /**
     * Spring 注入构造器，使用线程休眠实现真实的轮询等待。
     *
     * @param objectMapper 解析健康响应 JSON，复用容器中的共享实例
     * @param properties   超时与目标清单配置
     */
    @Autowired
    public ServiceHealthChecker(ObjectMapper objectMapper, ServiceHealthProperties properties) {
        this(objectMapper, properties, Thread::sleep);
    }

    /**
     * 测试用构造器，可替换休眠实现以避免真实等待。
     *
     * @param objectMapper JSON 解析器
     * @param properties   超时配置
     * @param sleeper      休眠策略
     */
    ServiceHealthChecker(ObjectMapper objectMapper,
                         ServiceHealthProperties properties,
                         Sleeper sleeper) {
        this.objectMapper = objectMapper;
        this.properties = properties;
        this.sleeper = sleeper;
    }

    /**
     * 探测一个目标并记录一行健康日志。
     *
     * @param definition 目标名称与绝对健康地址
     * @return 单目标结果；网络失败同样返回结果对象，不抛出异常
     */
    public ServiceHealthResult check(ServiceHealthDefinition definition) {
        ServiceHealthResult result = probe(definition);
        // 日志只记录固定检查结果，不输出 URL 中可能包含的凭据。
        log.info("[健康检查][项目={}] 状态={} HTTP={} 耗时={}ms 说明={}",
                definition.getName(), result.isHealthy() ? "在线" : "离线",
                result.getStatusCode() == null ? "-" : result.getStatusCode(),
                result.getDurationMs(), result.getMessage() == null ? "正常" : result.getMessage());
        return result;
    }

    /**
     * 执行一次 HTTP 健康探测。
     *
     * <p>按顺序处理四类失败：非 2xx 直接判定离线；响应体不是合法 JSON 或缺少布尔
     * {@code success=true} 视为无效响应；连接或读取超时记为 {@code Timed out}；
     * 连接被拒绝及其它 IO 异常记为 {@code Connection failed}。{@code disconnect()}
     * 放在 finally 中，避免反复巡检泄漏 socket 句柄。</p>
     *
     * @param definition 目标名称与健康地址
     * @return 带状态码、耗时和失败原因的探测结果
     */
    private ServiceHealthResult probe(ServiceHealthDefinition definition) {
        long startedAt = System.nanoTime();
        HttpURLConnection connection = null;
        Integer statusCode = null;
        try {
            connection = (HttpURLConnection) new URL(definition.getUrl()).openConnection();
            connection.setRequestMethod("GET");
            connection.setConnectTimeout(properties.getConnectTimeoutMs());
            connection.setReadTimeout(properties.getReadTimeoutMs());
            connection.setUseCaches(false);

            statusCode = connection.getResponseCode();
            if (statusCode < 200 || statusCode >= 300) {
                return ServiceHealthResult.unhealthy(
                        definition, statusCode, elapsedMillis(startedAt), "HTTP " + statusCode);
            }

            try (InputStream body = connection.getInputStream()) {
                JsonNode root = objectMapper.readTree(body);
                JsonNode success = root == null ? null : root.get("success");
                if (success == null || !success.isBoolean() || !success.booleanValue()) {
                    return invalidResponse(definition, statusCode, startedAt);
                }
            } catch (JsonProcessingException e) {
                return invalidResponse(definition, statusCode, startedAt);
            }

            return ServiceHealthResult.healthy(definition, statusCode, elapsedMillis(startedAt));
        } catch (SocketTimeoutException e) {
            return ServiceHealthResult.unhealthy(
                    definition, statusCode, elapsedMillis(startedAt), "Timed out");
        } catch (ConnectException e) {
            return ServiceHealthResult.unhealthy(
                    definition, statusCode, elapsedMillis(startedAt), "Connection failed");
        } catch (IOException e) {
            return ServiceHealthResult.unhealthy(
                    definition, statusCode, elapsedMillis(startedAt), "Connection failed");
        } finally {
            if (connection != null) {
                connection.disconnect();
            }
        }
    }

    /**
     * 轮询直到目标健康或超时。
     *
     * <p>尝试次数等于 {@code timeoutSeconds}，每次之间间隔 1 秒，首次探测立即执行，
     * 适合子服务拉起后的就绪确认。单次探测自身还受连接/读取超时约束，因此实际总耗时
     * 可能明显超过配置的秒数。线程被中断时恢复中断标记并立即返回 {@code false}，
     * 由调用方决定是否告警。</p>
     *
     * @param definition     目标名称与健康地址
     * @param timeoutSeconds 最多尝试次数，小于 1 时按 1 次处理
     * @return 超时前探测到健康返回 {@code true}，否则 {@code false}
     */
    public boolean waitUntilHealthy(ServiceHealthDefinition definition, int timeoutSeconds) {
        int attempts = Math.max(1, timeoutSeconds);
        for (int attempt = 0; attempt < attempts; attempt++) {
            if (check(definition).isHealthy()) {
                return true;
            }
            if (attempt + 1 >= attempts) {
                break;
            }
            try {
                sleeper.sleep(1000L);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return false;
            }
        }
        return false;
    }

    /**
     * 拼装本机健康检查地址。
     *
     * <p>主机固定为 {@code 127.0.0.1}，路径缺少前导斜杠时自动补齐。用于两个自动启动器与
     * 本机服务适配地址，不接受外部传入的主机名，避免探测被引向任意主机。</p>
     *
     * @param port       目标端口
     * @param healthPath 健康路径，例如 {@code /api/health}
     * @return 形如 {@code http://127.0.0.1:5174/api/health} 的绝对地址
     */
    public String buildLocalUrl(int port, String healthPath) {
        String normalizedPath = healthPath.startsWith("/") ? healthPath : "/" + healthPath;
        return "http://127.0.0.1:" + port + normalizedPath;
    }

    /**
     * 构造「响应格式不符合约定」的离线结果。
     *
     * @param definition 目标定义
     * @param statusCode 已取得的 HTTP 状态码
     * @param startedAt  探测开始时的 {@link System#nanoTime()} 基准
     * @return 带固定提示 {@code Invalid health response} 的离线结果
     */
    private ServiceHealthResult invalidResponse(ServiceHealthDefinition definition,
                                                Integer statusCode,
                                                long startedAt) {
        return ServiceHealthResult.unhealthy(
                definition, statusCode, elapsedMillis(startedAt), "Invalid health response");
    }

    private long elapsedMillis(long startedAt) {
        return TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - startedAt);
    }
}
