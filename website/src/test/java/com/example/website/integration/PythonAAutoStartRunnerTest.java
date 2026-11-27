package com.example.website.integration;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.test.util.ReflectionTestUtils;

import java.io.File;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;

/**
 * {@link PythonAAutoStartRunner} 的单元测试。
 *
 * <p>被测对象是 website 的自动启动适配层。本类只验证它交给操作系统的解释器、参数与工作目录，
 * 不启动 Python、不绑定端口、不访问网络：与进程相关的断言只检查尚未执行的
 * {@link ProcessBuilder}，与目录相关的断言用 {@link TempDir} 造假目录。</p>
 *
 * <p>固定的关键分支：</p>
 * <ul>
 *   <li>{@code log-to-console=true} 时输出重定向为 {@code INHERIT}，并注入
 *       {@code PORT=5174} 与 {@code PYTHONUNBUFFERED=1}，否则控制台看不到实时请求日志；</li>
 *   <li>工作目录下存在 {@code .venv/Scripts/python.exe} 时优先使用它，而不是配置的
 *       {@code python}；</li>
 *   <li>{@code run()} 在命令不存在时只告警不抛异常，自动启动失败不能让 website 起不来；</li>
 *   <li>从仓库根目录与 {@code website} 模块目录启动时都能解析到 {@code website/python-a}，
 *       因为 IDE 与命令行给出的 {@code user.dir} 不同。</li>
 * </ul>
 */
class PythonAAutoStartRunnerTest {

    @Test
    void createsPythonAProcessBuilderWithConsoleLogging() {
        PythonAAutoStartRunner runner = new PythonAAutoStartRunner();
        ReflectionTestUtils.setField(runner, "command", "python");
        ReflectionTestUtils.setField(runner, "port", 5174);
        ReflectionTestUtils.setField(runner, "logToConsole", true);
        File directory = new File("website/python-a");

        ProcessBuilder builder = runner.createProcessBuilder(directory);

        assertThat(builder.directory()).isEqualTo(directory);
        assertThat(builder.command()).containsSubsequence("server.py");
        assertThat(builder.environment()).containsEntry("PORT", "5174");
        assertThat(builder.environment()).containsEntry("PYTHONUNBUFFERED", "1");
        assertThat(builder.redirectOutput()).isEqualTo(ProcessBuilder.Redirect.INHERIT);
        assertThat(builder.redirectError()).isEqualTo(ProcessBuilder.Redirect.INHERIT);
    }

    @Test
    void prefersPythonALocalVirtualEnvironmentWhenResolvingPythonCommand(@TempDir Path tempDir) throws Exception {
        Path pythonPath = tempDir.resolve(".venv").resolve("Scripts").resolve("python.exe");
        Files.createDirectories(pythonPath.getParent());
        Files.createFile(pythonPath);

        PythonAAutoStartRunner runner = new PythonAAutoStartRunner();
        ReflectionTestUtils.setField(runner, "command", "python");
        ReflectionTestUtils.setField(runner, "port", 5174);
        ReflectionTestUtils.setField(runner, "logToConsole", true);

        ProcessBuilder builder = runner.createProcessBuilder(tempDir.toFile());

        assertThat(builder.command()).startsWith(pythonPath.toFile().getAbsolutePath());
        assertThat(builder.command()).containsSubsequence("server.py");
    }

    @Test
    void doesNotFailWebsiteWhenPythonCommandCannotStart(@TempDir Path tempDir) {
        PythonAAutoStartRunner runner = new PythonAAutoStartRunner();
        ReflectionTestUtils.setField(runner, "workDir", tempDir.toString());
        ReflectionTestUtils.setField(runner, "command", "missing-python-command-for-test");
        ReflectionTestUtils.setField(runner, "port", 5174);
        ReflectionTestUtils.setField(runner, "healthPath", "/api/health");
        ReflectionTestUtils.setField(runner, "startupTimeoutSeconds", 1);
        ReflectionTestUtils.setField(runner, "logToConsole", true);

        assertThatCode(() -> runner.run(null)).doesNotThrowAnyException();
    }

    @Test
    void resolvesPythonAUnderWebsiteWhenStartedFromRepositoryRoot() throws Exception {
        String originalUserDir = System.getProperty("user.dir");
        try {
            System.setProperty("user.dir", resolveRepositoryRoot().getCanonicalPath());
            PythonAAutoStartRunner runner = new PythonAAutoStartRunner();
            ReflectionTestUtils.setField(runner, "workDir", "website/python-a");

            File directory = runner.resolveWorkDir();

            assertThat(directory).isDirectory();
            assertThat(new File(directory, "server.py")).isFile();
            assertThat(directory.getPath().replace('\\', '/')).endsWith("website/python-a");
        } finally {
            System.setProperty("user.dir", originalUserDir);
        }
    }

    @Test
    void resolvesPythonAUnderWebsiteWhenStartedFromWebsiteDirectory() throws Exception {
        String originalUserDir = System.getProperty("user.dir");
        try {
            System.setProperty("user.dir", resolveWebsiteDir().getCanonicalPath());
            PythonAAutoStartRunner runner = new PythonAAutoStartRunner();
            ReflectionTestUtils.setField(runner, "workDir", "website/python-a");

            File directory = runner.resolveWorkDir();

            assertThat(directory).isDirectory();
            assertThat(new File(directory, "server.py")).isFile();
            assertThat(directory.getPath().replace('\\', '/')).endsWith("website/python-a");
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
}
