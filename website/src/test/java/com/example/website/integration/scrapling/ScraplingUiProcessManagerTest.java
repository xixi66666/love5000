package com.example.website.integration.scrapling;

import com.example.website.integration.health.ServiceHealthChecker;
import com.example.website.integration.health.ServiceHealthDefinition;
import com.example.website.integration.health.ServiceHealthResult;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.File;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * {@link ScraplingUiProcessManager} 的单元测试。
 *
 * <p>被测对象在首页卡片点击时拉起 {@code website/scrapling-ui} 的 FastAPI 服务。本类不启动
 * Python、不连接 5176、不启动 Playwright：健康检查由 mock 固定为不健康，让 {@code start()}
 * 走启动分支；{@code createProcessBuilder} 的入参是 {@code backend} 目录，用例直接把
 * {@link TempDir} 当作 backend 目录来验证解释器选择。</p>
 *
 * <p>固定的解释器矩阵：默认命令 {@code uv} 时优先 {@code .venv} 内的解释器，缺失才回退
 * {@code uv run python}；显式配置全局 Python（包括带空格的绝对路径）时直接执行该命令并追加
 * {@code -m uvicorn}，绕过 {@code .venv}；绝对路径的 {@code uv.exe} 仍按 uv 处理。
 * 同时固定三个 UTF-8 环境变量、{@code INHERIT} 日志、已在线复用，以及缺少 backend、
 * 未构建 dist、启动器不可执行时的可读提示与工作目录解析。</p>
 */
class ScraplingUiProcessManagerTest {

    @Test
    void createsUvicornProcessBuilderWithBackendVirtualEnvironment(@TempDir Path tempDir) throws Exception {
        Path pythonPath = tempDir.resolve(".venv").resolve("Scripts").resolve("python.exe");
        Files.createDirectories(pythonPath.getParent());
        Files.createFile(pythonPath);

        ScraplingUiProcessManager manager = newManager(mockChecker(), properties(tempDir, "uv"));

        ProcessBuilder builder = manager.createProcessBuilder(tempDir.toFile());

        assertThat(builder.directory()).isEqualTo(tempDir.toFile());
        assertThat(builder.command()).startsWith(pythonPath.toFile().getAbsolutePath());
        assertThat(builder.command()).containsSubsequence(
                "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "5176");
        assertThat(builder.environment()).containsEntry("PYTHONUTF8", "1");
        assertThat(builder.environment()).containsEntry("PYTHONIOENCODING", "utf-8");
        assertThat(builder.environment()).containsEntry("PYTHONUNBUFFERED", "1");
        assertThat(builder.redirectOutput()).isEqualTo(ProcessBuilder.Redirect.INHERIT);
        assertThat(builder.redirectError()).isEqualTo(ProcessBuilder.Redirect.INHERIT);
    }

    @Test
    void fallsBackToUvRunPythonWhenVirtualEnvironmentMissing(@TempDir Path tempDir) {
        ScraplingUiProcessManager manager = newManager(mockChecker(), properties(tempDir, "uv"));

        ProcessBuilder builder = manager.createProcessBuilder(tempDir.toFile());

        assertThat(builder.command()).startsWith("uv", "run", "python");
        assertThat(builder.command()).containsSubsequence("main:app", "--port", "5176");
    }

    @Test
    void usesConfiguredGlobalPythonEvenWhenVirtualEnvironmentExists(@TempDir Path tempDir) throws Exception {
        Path venvPython = tempDir.resolve(".venv").resolve("Scripts").resolve("python.exe");
        Files.createDirectories(venvPython.getParent());
        Files.createFile(venvPython);
        String globalPython = tempDir.resolve("Global Python").resolve("python.exe").toString();
        ScraplingUiProcessManager manager = newManager(mockChecker(), properties(tempDir, globalPython));

        ProcessBuilder builder = manager.createProcessBuilder(tempDir.toFile());

        assertThat(builder.command()).startsWith(globalPython, "-m", "uvicorn");
        assertThat(builder.command()).doesNotContain("run", "python", venvPython.toString());
    }

    @Test
    void usesGlobalPythonCommandWithoutUvArguments(@TempDir Path tempDir) {
        ScraplingUiProcessManager manager = newManager(mockChecker(), properties(tempDir, "python"));

        ProcessBuilder builder = manager.createProcessBuilder(tempDir.toFile());

        assertThat(builder.command()).startsWith("python", "-m", "uvicorn");
    }

    @Test
    void supportsAbsoluteUvExecutablePath(@TempDir Path tempDir) {
        String uvCommand = tempDir.resolve("Tools").resolve("uv.exe").toString();
        ScraplingUiProcessManager manager = newManager(mockChecker(), properties(tempDir, uvCommand));

        assertThat(manager.createProcessBuilder(tempDir.toFile()).command())
                .startsWith(uvCommand, "run", "python", "-m", "uvicorn");
    }

    @Test
    void returnsAlreadyRunningWhenHealthCheckSucceeds() {
        ServiceHealthChecker checker = mockChecker();
        when(checker.check(any(ServiceHealthDefinition.class)))
                .thenReturn(ServiceHealthResult.healthy(
                        new ServiceHealthDefinition("scrapling-ui", "http://127.0.0.1:5176/api/health"), 200, 5));
        ScraplingUiProcessManager manager = newManager(checker, new ScraplingUiProperties());

        ScraplingUiStartResult result = manager.start();

        assertThat(result.getStatus()).isEqualTo(ScraplingUiStartResult.STATUS_ALREADY_RUNNING);
        assertThat(result.getUrl()).isEqualTo("http://127.0.0.1:5176/");
    }

    @Test
    void failsWithReadableMessageWhenFrontendBuildIsMissing(@TempDir Path tempDir) throws Exception {
        Files.createDirectories(tempDir.resolve("backend"));
        ScraplingUiProcessManager manager = newManager(mockChecker(), properties(tempDir, "uv"));

        assertThatThrownBy(manager::start)
                .isInstanceOf(ScraplingUiStartException.class)
                .hasMessageContaining("前端尚未构建");
    }

    @Test
    void failsWithReadableMessageWhenBackendDirectoryIsMissing(@TempDir Path tempDir) {
        ScraplingUiProcessManager manager = newManager(mockChecker(), properties(tempDir, "uv"));

        assertThatThrownBy(manager::start)
                .isInstanceOf(ScraplingUiStartException.class)
                .hasMessageContaining("后端目录不存在");
    }

    @Test
    void failsWithReadableMessageWhenLauncherCannotStart(@TempDir Path tempDir) throws Exception {
        Files.createDirectories(tempDir.resolve("backend"));
        Files.createDirectories(tempDir.resolve("frontend").resolve("dist"));
        Files.createFile(tempDir.resolve("frontend").resolve("dist").resolve("index.html"));
        ScraplingUiProcessManager manager = newManager(mockChecker(), properties(tempDir, "missing-launcher-for-test"));

        assertThatThrownBy(manager::start)
                .isInstanceOf(ScraplingUiStartException.class)
                .hasMessageContaining("uv sync");
    }

    @Test
    void resolvesWorkDirUnderWebsiteWhenStartedFromRepositoryRoot() throws Exception {
        String originalUserDir = System.getProperty("user.dir");
        try {
            System.setProperty("user.dir", resolveRepositoryRoot().getCanonicalPath());
            ScraplingUiProperties properties = new ScraplingUiProperties();
            ScraplingUiProcessManager manager = newManager(mockChecker(), properties);

            File directory = manager.resolveWorkDir();

            assertThat(directory).isDirectory();
            assertThat(new File(directory, "backend").isDirectory()).isTrue();
            assertThat(directory.getPath().replace('\\', '/')).endsWith("website/scrapling-ui");
        } finally {
            System.setProperty("user.dir", originalUserDir);
        }
    }

    @Test
    void resolvesWorkDirUnderWebsiteWhenStartedFromWebsiteDirectory() throws Exception {
        String originalUserDir = System.getProperty("user.dir");
        try {
            System.setProperty("user.dir", resolveWebsiteDir().getCanonicalPath());
            ScraplingUiProperties properties = new ScraplingUiProperties();
            ScraplingUiProcessManager manager = newManager(mockChecker(), properties);

            File directory = manager.resolveWorkDir();

            assertThat(directory).isDirectory();
            assertThat(new File(directory, "backend").isDirectory()).isTrue();
            assertThat(directory.getPath().replace('\\', '/')).endsWith("website/scrapling-ui");
        } finally {
            System.setProperty("user.dir", originalUserDir);
        }
    }

    private ScraplingUiProcessManager newManager(ServiceHealthChecker checker, ScraplingUiProperties properties) {
        return new ScraplingUiProcessManager(checker, properties);
    }

    /**
     * 造一个固定返回「不健康」的健康检查器。
     *
     * <p>避免 {@code start()} 直接走「已在线复用」的短路分支，从而真正验证启动前置校验与错误提示；
     * 也确保测试不会去请求 5176。</p>
     *
     * @return 固定返回不健康结果的 mock
     */
    private ServiceHealthChecker mockChecker() {
        ServiceHealthChecker checker = mock(ServiceHealthChecker.class);
        when(checker.check(any(ServiceHealthDefinition.class)))
                .thenReturn(ServiceHealthResult.unhealthy(
                        new ServiceHealthDefinition("scrapling-ui", "http://127.0.0.1:5176/api/health"),
                        null, 3, "Connection failed"));
        return checker;
    }

    /**
     * 构造指向临时目录的配置。
     *
     * <p>启动超时压到 1 秒，让「未就绪」分支不必等默认 90 秒；{@code command} 决定解释器选择分支，
     * 传入不存在的命令即可模拟启动器缺失。</p>
     *
     * @param workDir 临时工作目录，用例用它模拟 {@code website/scrapling-ui}
     * @param command 命令配置，可为 {@code uv}、{@code python}、绝对路径或不存在的命令
     * @return 已填好工作目录、命令与超时的配置
     */
    private ScraplingUiProperties properties(Path workDir, String command) {
        ScraplingUiProperties properties = new ScraplingUiProperties();
        properties.setWorkDir(workDir.toAbsolutePath().toString());
        properties.setCommand(command);
        properties.setStartupTimeoutSeconds(1);
        return properties;
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
