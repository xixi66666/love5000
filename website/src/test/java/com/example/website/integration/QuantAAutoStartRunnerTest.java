package com.example.website.integration;

import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import com.sun.net.httpserver.HttpServer;
import java.io.File;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import org.junit.jupiter.api.io.TempDir;

/**
 * {@link QuantAAutoStartRunner} 的单元测试。
 *
 * <p>被测对象在 website 启动阶段拉起或复用 {@code website/quant-a}（FastAPI + uvicorn，5175）。
 * 本类不启动 Python、不占用 5175：命令类断言只检查尚未执行的 {@link ProcessBuilder}，
 * 目录类断言用 {@link TempDir} 造假目录。</p>
 *
 * <p>固定的关键分支：</p>
 * <ul>
 *   <li>健康地址由端口与 {@code health-path} 拼成，路径缺少前导斜杠时自动补齐；</li>
 *   <li>命令固定为 {@code -m uvicorn main:app --host 127.0.0.1 --port 5175}，
 *       只监听回环地址、不执行 {@code server.py}，并注入 {@code PYTHONUNBUFFERED=1}；</li>
 *   <li>工作目录存在 {@code .venv} 时优先使用其中的解释器；</li>
 *   <li>命令不存在时 {@code run()} 只告警，不阻断 website 启动；</li>
 *   <li>仓库根目录与 {@code website} 模块目录两种启动位置下都能解析工作目录；</li>
 *   <li>健康判定必须看响应体：HTTP 200 但 {@code success=false} 不算健康。</li>
 * </ul>
 */
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
        assertThat(builder.command()).containsSubsequence(
                "-m",
                "uvicorn",
                "main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "5175"
        );
        assertThat(builder.environment()).containsEntry("PYTHONUNBUFFERED", "1");

        assertThat(builder.command()).doesNotContain("server.py");
        assertThat(builder.redirectOutput()).isEqualTo(ProcessBuilder.Redirect.INHERIT);
        assertThat(builder.redirectError()).isEqualTo(ProcessBuilder.Redirect.INHERIT);
    }

    @Test
    void prefersQuantLocalVirtualEnvironmentWhenResolvingPythonCommand(@TempDir Path tempDir) throws Exception {
        Path pythonPath = tempDir.resolve(".venv").resolve("Scripts").resolve("python.exe");
        Files.createDirectories(pythonPath.getParent());
        Files.createFile(pythonPath);

        QuantAAutoStartRunner runner = new QuantAAutoStartRunner();
        ReflectionTestUtils.setField(runner, "command", "python");
        ReflectionTestUtils.setField(runner, "port", 5175);
        ReflectionTestUtils.setField(runner, "logToConsole", true);

        ProcessBuilder builder = runner.createProcessBuilder(tempDir.toFile());

        assertThat(builder.command()).startsWith(pythonPath.toFile().getAbsolutePath());
        assertThat(builder.command()).containsSubsequence("-m", "uvicorn", "main:app");
    }

    @Test
    void doesNotFailWebsiteWhenQuantPythonCommandCannotStart(@TempDir Path tempDir) {
        QuantAAutoStartRunner runner = new QuantAAutoStartRunner();
        ReflectionTestUtils.setField(runner, "workDir", tempDir.toString());
        ReflectionTestUtils.setField(runner, "command", "missing-python-command-for-test");
        ReflectionTestUtils.setField(runner, "port", 5175);
        ReflectionTestUtils.setField(runner, "healthPath", "/api/health");
        ReflectionTestUtils.setField(runner, "startupTimeoutSeconds", 1);
        ReflectionTestUtils.setField(runner, "logToConsole", true);

        assertThatCode(() -> runner.run(null)).doesNotThrowAnyException();
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

    /**
     * 定位 {@code website} 模块目录。
     *
     * <p>测试可能从仓库根目录或模块目录运行；当前目录名已是 {@code website} 时不能再拼一层，
     * 否则会得到不存在的 {@code website/website}。</p>
     *
     * @return {@code website} 模块目录
     */
    private File resolveWebsiteDir() {
        File currentDir = new File(System.getProperty("user.dir"));
        if ("website".equals(currentDir.getName())) {
            return currentDir;
        }
        return new File(currentDir, "website");
    }

    /**
     * 由 {@code website} 目录上溯到仓库根目录。
     *
     * <p>供临时改写 {@code user.dir} 的用例使用，用完必须在 {@code finally} 中还原。</p>
     *
     * @return 仓库根目录
     */
    private File resolveRepositoryRoot() {
        File websiteDir = resolveWebsiteDir();
        return websiteDir.getParentFile();
    }

    @Test
    void healthCheckRequiresSuccessTruePayload() throws Exception {
        // 绑定 127.0.0.1:0 由系统分配空闲端口，不碰真实服务的 5175；响应体故意返回
        // 200 + success=false，用来固定「只看状态码会把故障实例当成健康」这条边界。
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
