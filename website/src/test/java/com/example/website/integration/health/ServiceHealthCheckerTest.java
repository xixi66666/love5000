package com.example.website.integration.health;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 单体健康探测 {@link ServiceHealthChecker} 的单元测试。
 *
 * <p>钉住判定规则与失败文案：只有 HTTP 2xx 且响应顶层的 {@code success} 是布尔 {@code true}
 * 才算在线；非 2xx 记为 {@code HTTP} 加状态码；JSON 损坏、缺少 {@code success}、或
 * {@code success} 不是布尔（例如字符串 {@code "true"}）统一记 {@code Invalid health response}；
 * 连接失败与读超时分别记 {@code Connection failed} / {@code Timed out}，两者都不把底层异常
 * 细节写进结果，避免把地址或凭据带进日志和接口。</p>
 *
 * <p>另外覆盖 {@code buildLocalUrl} 的前导斜杠归一化，以及 {@code waitUntilHealthy} 的三条轮询语义：
 * 至少探测一次、超时返回 {@code false}、被中断时保留线程的 interrupt 标志。
 * 日志格式也在断言范围内：必须带 {@code [健康检查][项目=...]}，否则 11 个目标并发巡检时无法定位。</p>
 *
 * <p>隔离：用 JDK 自带的 {@code com.sun.net.httpserver.HttpServer} 在 127.0.0.1 的随机端口
 * 伪装上游，超时压到 200ms，不访问任何真实服务、不连 MySQL。轮询用例通过包内构造器注入假的
 * {@code Sleeper}（空实现或直接抛中断），既不真的睡 1 秒，也不会让用例变慢。</p>
 */
class ServiceHealthCheckerTest {

    private HttpServer server;

    @Test
    @org.junit.jupiter.api.extension.ExtendWith(org.springframework.boot.test.system.OutputCaptureExtension.class)
    void consoleLogsIdentifyTheCheckedProject(org.springframework.boot.test.system.CapturedOutput output) throws Exception {
        String url = serve(200, "{\"success\":true}");
        checker().check(new ServiceHealthDefinition("skill-finder", url));
        // 排障要求：日志必须带项目名，否则多目标并发巡检时分不清是谁失败。
        assertThat(output.getOut()).contains("[健康检查][项目=skill-finder]", "状态=在线", "HTTP=200");
    }

    @AfterEach
    void stopServer() {
        if (server != null) {
            server.stop(0);
        }
    }

    @Test
    void acceptsOnlyTwoXxWithBooleanSuccessTrue() throws Exception {
        String url = serve(200, "{\"success\":true,\"service\":\"demo\"}");

        ServiceHealthResult result = checker().check(new ServiceHealthDefinition("demo", url));

        assertThat(result.isHealthy()).isTrue();
        assertThat(result.getStatusCode()).isEqualTo(200);
        assertThat(result.getDurationMs()).isGreaterThanOrEqualTo(0);
        assertThat(result.getMessage()).isNull();
    }

    @Test
    void rejectsNonTwoXxResponses() throws Exception {
        String url = serve(503, "{\"success\":true}");

        ServiceHealthResult result = checker().check(new ServiceHealthDefinition("demo", url));

        assertThat(result.isHealthy()).isFalse();
        assertThat(result.getStatusCode()).isEqualTo(503);
        assertThat(result.getMessage()).isEqualTo("HTTP 503");
    }

    @Test
    void rejectsMalformedOrNonBooleanSuccessPayloads() throws Exception {
        // 字符串 "true" 也算无效：只认布尔类型，防止上游把标志位当字符串返回。
        assertInvalidPayload("{");
        assertInvalidPayload("{}");
        assertInvalidPayload("{\"success\":false}");
        assertInvalidPayload("{\"success\":\"true\"}");
    }

    @Test
    void classifiesConnectionFailuresWithoutLeakingExceptionDetails() throws Exception {
        java.net.ServerSocket socket = new java.net.ServerSocket(0);
        int unusedPort = socket.getLocalPort();
        socket.close();
        ServiceHealthDefinition definition = new ServiceHealthDefinition(
                "offline", "http://127.0.0.1:" + unusedPort + "/api/health");

        ServiceHealthResult result = checker().check(definition);

        assertThat(result.isHealthy()).isFalse();
        assertThat(result.getStatusCode()).isNull();
        assertThat(result.getMessage()).isIn("Connection failed", "Timed out");
    }

    @Test
    void classifiesReadTimeouts() throws Exception {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/api/health", exchange -> {
            try {
                Thread.sleep(400);
                byte[] body = "{\"success\":true}".getBytes(StandardCharsets.UTF_8);
                exchange.sendResponseHeaders(200, body.length);
                exchange.getResponseBody().write(body);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            } finally {
                exchange.close();
            }
        });
        server.start();
        String url = "http://127.0.0.1:" + server.getAddress().getPort() + "/api/health";

        ServiceHealthResult result = checker().check(new ServiceHealthDefinition("slow", url));

        assertThat(result.isHealthy()).isFalse();
        assertThat(result.getMessage()).isEqualTo("Timed out");
    }

    @Test
    void normalizesLocalHealthUrls() {
        ServiceHealthChecker checker = checker();

        assertThat(checker.buildLocalUrl(5174, "api/health"))
                .isEqualTo("http://127.0.0.1:5174/api/health");
        assertThat(checker.buildLocalUrl(5174, "/api/health"))
                .isEqualTo("http://127.0.0.1:5174/api/health");
    }

    @Test
    void readinessPollingStopsAfterAnEventuallyHealthyResponse() {
        AtomicInteger checks = new AtomicInteger();
        ServiceHealthDefinition definition = new ServiceHealthDefinition(
                "demo", "http://127.0.0.1/api/health");
        ServiceHealthChecker checker = recordingChecker(checks, definition, 3);

        assertThat(checker.waitUntilHealthy(definition, 5)).isTrue();
        assertThat(checks.get()).isEqualTo(3);
    }

    @Test
    void readinessPollingUsesAtLeastOneAttemptAndHonorsTimeout() {
        AtomicInteger checks = new AtomicInteger();
        ServiceHealthDefinition definition = new ServiceHealthDefinition(
                "demo", "http://127.0.0.1/api/health");
        ServiceHealthChecker checker = recordingChecker(checks, definition, Integer.MAX_VALUE);

        assertThat(checker.waitUntilHealthy(definition, 0)).isFalse();
        assertThat(checks.get()).isEqualTo(1);
    }

    @Test
    void readinessPollingPreservesInterruptStatus() {
        ServiceHealthProperties properties = new ServiceHealthProperties();
        ServiceHealthDefinition definition = new ServiceHealthDefinition(
                "demo", "http://127.0.0.1/api/health");
        ServiceHealthChecker checker = new ServiceHealthChecker(
                new ObjectMapper(), properties, millis -> {
                    throw new InterruptedException("test");
                }) {
            @Override
            public ServiceHealthResult check(ServiceHealthDefinition ignored) {
                return ServiceHealthResult.unhealthy(definition, null, 0, "offline");
            }
        };

        assertThat(checker.waitUntilHealthy(definition, 2)).isFalse();
        assertThat(Thread.currentThread().isInterrupted()).isTrue();
        // 断言后必须清掉中断标志，否则同一线程上后续用例会被莫名打断。
        Thread.interrupted();
    }

    /**
     * 断言某种坏响应体被判为无效。
     *
     * <p>每种负载都要单独起一个假上游：断言后立刻停服并清空字段，
     * 这样同一用例可以连续覆盖多种负载，又不会让 {@link #stopServer()} 重复关同一个 server。</p>
     */
    private void assertInvalidPayload(String payload) throws Exception {
        String url = serve(200, payload);
        ServiceHealthResult result = checker().check(new ServiceHealthDefinition("demo", url));
        assertThat(result.isHealthy()).isFalse();
        assertThat(result.getMessage()).isEqualTo("Invalid health response");
        server.stop(0);
        server = null;
    }

    /** 起一个只在 127.0.0.1 随机端口、按固定状态码和负载应答的假上游，返回其健康检查地址。 */
    private String serve(int status, String payload) throws IOException {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/api/health", exchange -> {
            byte[] body = payload.getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().set("Content-Type", "application/json");
            exchange.sendResponseHeaders(status, body.length);
            exchange.getResponseBody().write(body);
            exchange.close();
        });
        server.start();
        return "http://127.0.0.1:" + server.getAddress().getPort() + "/api/health";
    }

    /** 连接与读取超时都压到 200ms 的 checker，保证超时类用例秒级结束。 */
    private ServiceHealthChecker checker() {
        ServiceHealthProperties properties = new ServiceHealthProperties();
        properties.setConnectTimeoutMs(200);
        properties.setReadTimeoutMs(200);
        return new ServiceHealthChecker(new ObjectMapper(), properties);
    }

    /**
     * 造一个只数调用次数、不真的发请求的 checker。
     *
     * <p>第 {@code healthyAttempt} 次起返回健康，之前都返回离线；{@code Sleeper} 是空实现，
     * 于是「失败后等 1 秒再试」不会真的等待。用匿名子类覆盖 {@code check}，
     * 才能精确验证轮询次数与提前退出。</p>
     */
    private ServiceHealthChecker recordingChecker(AtomicInteger checks,
                                                   ServiceHealthDefinition definition,
                                                   int healthyAttempt) {
        ServiceHealthProperties properties = new ServiceHealthProperties();
        return new ServiceHealthChecker(new ObjectMapper(), properties, millis -> {
        }) {
            @Override
            public ServiceHealthResult check(ServiceHealthDefinition ignored) {
                int attempt = checks.incrementAndGet();
                if (attempt >= healthyAttempt) {
                    return ServiceHealthResult.healthy(definition, 200, 0);
                }
                return ServiceHealthResult.unhealthy(definition, null, 0, "offline");
            }
        };
    }
}
