package com.example.website.integration;

import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.io.File;
import java.io.OutputStream;
import java.net.InetSocketAddress;

import static org.assertj.core.api.Assertions.assertThat;

class VideoAutoStartRunnerTest {

    @Test
    void buildsVideoHealthUrlFromConfiguredPortAndPath() {
        VideoAutoStartRunner runner = new VideoAutoStartRunner();
        ReflectionTestUtils.setField(runner, "port", 5176);
        ReflectionTestUtils.setField(runner, "healthPath", "api/health");

        String healthUrl = runner.buildHealthUrl();

        assertThat(healthUrl).isEqualTo("http://127.0.0.1:5176/api/health");
    }

    @Test
    void createsVideoWebServerProcessBuilderInVideoDirectory() {
        VideoAutoStartRunner runner = new VideoAutoStartRunner();
        ReflectionTestUtils.setField(runner, "command", "python");
        ReflectionTestUtils.setField(runner, "port", 5176);
        ReflectionTestUtils.setField(runner, "logToConsole", true);
        File directory = new File("website/video");

        ProcessBuilder builder = runner.createProcessBuilder(directory);

        assertThat(builder.directory()).isEqualTo(directory);
        assertThat(builder.command()).containsExactly(
                "python",
                "web_server.py",
                "--host",
                "127.0.0.1",
                "--port",
                "5176"
        );
        assertThat(builder.environment()).containsEntry("PYTHONUNBUFFERED", "1");
        assertThat(builder.redirectOutput()).isEqualTo(ProcessBuilder.Redirect.INHERIT);
        assertThat(builder.redirectError()).isEqualTo(ProcessBuilder.Redirect.INHERIT);
    }

    @Test
    void resolvesVideoUnderWebsiteWhenStartedFromRepositoryRoot() throws Exception {
        String originalUserDir = System.getProperty("user.dir");
        try {
            System.setProperty("user.dir", resolveRepositoryRoot().getCanonicalPath());
            VideoAutoStartRunner runner = new VideoAutoStartRunner();
            ReflectionTestUtils.setField(runner, "workDir", "website/video");

            File directory = runner.resolveWorkDir();

            assertThat(directory).isDirectory();
            assertThat(new File(directory, "web_server.py")).isFile();
            assertThat(directory.getPath().replace('\\', '/')).endsWith("website/video");
        } finally {
            System.setProperty("user.dir", originalUserDir);
        }
    }

    @Test
    void resolvesVideoUnderWebsiteWhenStartedFromWebsiteDirectory() throws Exception {
        String originalUserDir = System.getProperty("user.dir");
        try {
            System.setProperty("user.dir", resolveWebsiteDir().getCanonicalPath());
            VideoAutoStartRunner runner = new VideoAutoStartRunner();
            ReflectionTestUtils.setField(runner, "workDir", "website/video");

            File directory = runner.resolveWorkDir();

            assertThat(directory).isDirectory();
            assertThat(new File(directory, "web_server.py")).isFile();
            assertThat(directory.getPath().replace('\\', '/')).endsWith("website/video");
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
            VideoAutoStartRunner runner = new VideoAutoStartRunner();

            boolean healthy = runner.isHealthy("http://127.0.0.1:" + server.getAddress().getPort() + "/api/health");

            assertThat(healthy).isFalse();
        } finally {
            server.stop(0);
        }
    }
}
