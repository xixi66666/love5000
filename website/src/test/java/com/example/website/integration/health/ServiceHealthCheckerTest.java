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

class ServiceHealthCheckerTest {

    private HttpServer server;

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
        Thread.interrupted();
    }

    private void assertInvalidPayload(String payload) throws Exception {
        String url = serve(200, payload);
        ServiceHealthResult result = checker().check(new ServiceHealthDefinition("demo", url));
        assertThat(result.isHealthy()).isFalse();
        assertThat(result.getMessage()).isEqualTo("Invalid health response");
        server.stop(0);
        server = null;
    }

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

    private ServiceHealthChecker checker() {
        ServiceHealthProperties properties = new ServiceHealthProperties();
        properties.setConnectTimeoutMs(200);
        properties.setReadTimeoutMs(200);
        return new ServiceHealthChecker(new ObjectMapper(), properties);
    }

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
