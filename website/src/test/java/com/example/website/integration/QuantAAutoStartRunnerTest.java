package com.example.website.integration;

import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import com.sun.net.httpserver.HttpServer;
import java.io.File;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class QuantAAutoStartRunnerTest {

    @Test
    void buildsQuantHealthUrlFromConfiguredPortAndPath() {
        QuantAAutoStartRunner runner = new QuantAAutoStartRunner();
        ReflectionTestUtils.setField(runner, "port", 5175);
        ReflectionTestUtils.setField(runner, "healthPath", "api/health");

        String healthUrl = runner.buildHealthUrl();

        assertThat(healthUrl).isEqualTo("http://127.0.0.1:5175/api/health");
    }

    @Test
    void createsUvicornProcessBuilderInQuantDirectory() {
        QuantAAutoStartRunner runner = new QuantAAutoStartRunner();
        ReflectionTestUtils.setField(runner, "command", "python");
        ReflectionTestUtils.setField(runner, "port", 5175);
        File directory = new File("quant-a");

        ProcessBuilder builder = runner.createProcessBuilder(directory);

        assertThat(builder.directory()).isEqualTo(directory);
        assertThat(builder.command()).containsExactly(
                "python",
                "-m",
                "uvicorn",
                "main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "5175"
        );
        assertThat(builder.environment()).containsEntry("PYTHONUNBUFFERED", "1");

        List<String> command = builder.command();
        assertThat(command).doesNotContain("server.py");
    }

    @Test
    void healthCheckRequiresSuccessTruePayload() throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/api/health", exchange -> {
            byte[] body = "{\"success\":false}".getBytes("UTF-8");
            exchange.sendResponseHeaders(200, body.length);
            try (OutputStream output = exchange.getResponseBody()) {
                output.write(body);
            }
        });
        server.start();

        try {
            QuantAAutoStartRunner runner = new QuantAAutoStartRunner();

            boolean healthy = runner.isHealthy("http://127.0.0.1:" + server.getAddress().getPort() + "/api/health");

            assertThat(healthy).isFalse();
        } finally {
            server.stop(0);
        }
    }
}
