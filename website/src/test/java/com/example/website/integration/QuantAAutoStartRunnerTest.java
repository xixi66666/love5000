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
        ReflectionTestUtils.setField(runner, "logToConsole", true);
        File directory = new File("website/quant-a");

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
        assertThat(builder.redirectOutput()).isEqualTo(ProcessBuilder.Redirect.INHERIT);
        assertThat(builder.redirectError()).isEqualTo(ProcessBuilder.Redirect.INHERIT);
    }

    @Test
    void resolvesQuantAUnderWebsiteWhenStartedFromRepositoryRoot() throws Exception {
        String originalUserDir = System.getProperty("user.dir");
        try {
            System.setProperty("user.dir", resolveRepositoryRoot().getCanonicalPath());
            QuantAAutoStartRunner runner = new QuantAAutoStartRunner();
            ReflectionTestUtils.setField(runner, "workDir", "website/quant-a");

            File directory = runner.resolveWorkDir();

            assertThat(directory).isDirectory();
            assertThat(new File(directory, "main.py")).isFile();
            assertThat(directory.getPath().replace('\\', '/')).endsWith("website/quant-a");
        } finally {
            System.setProperty("user.dir", originalUserDir);
        }
    }

    @Test
    void resolvesQuantAUnderWebsiteWhenStartedFromWebsiteDirectory() throws Exception {
        String originalUserDir = System.getProperty("user.dir");
        try {
            System.setProperty("user.dir", resolveWebsiteDir().getCanonicalPath());
            QuantAAutoStartRunner runner = new QuantAAutoStartRunner();
            ReflectionTestUtils.setField(runner, "workDir", "website/quant-a");

            File directory = runner.resolveWorkDir();

            assertThat(directory).isDirectory();
            assertThat(new File(directory, "main.py")).isFile();
            assertThat(directory.getPath().replace('\\', '/')).endsWith("website/quant-a");
        } finally {
            System.setProperty("user.dir", originalUserDir);
        }
    }

    private File resolveWebsiteDir() {
        File currentDir = new File(System.getProperty("user.dir"));
        if ("website".equals(currentDir.getName())) {
            return currentDir;
        }
        return new File(currentDir, "website");
    }

    private File resolveRepositoryRoot() {
        File websiteDir = resolveWebsiteDir();
        return websiteDir.getParentFile();
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
