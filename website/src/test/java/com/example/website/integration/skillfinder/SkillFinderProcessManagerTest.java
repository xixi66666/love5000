package com.example.website.integration.skillfinder;

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
 * {@link SkillFinderProcessManager} 的单元测试。
 *
 * <p>被测对象在首页卡片点击时拉起 {@code website/skill-finder}（FastAPI + uvicorn，
 * 模块名 {@code app.main:app}）。本类不启动 Python、不连接 5177、不连接共享 MySQL：
 * 健康检查由 mock 固定为不健康以进入启动分支；{@code createProcessBuilder} 的入参是
 * {@code backend} 目录，用例直接把 {@link TempDir} 当作 backend 目录。</p>
 *
 * <p>固定的关键分支：{@code uv} 时优先 {@code .venv} 解释器，缺失回退
 * {@code uv run python -m uvicorn app.main:app}；注入三个 UTF-8 环境变量并以
 * {@code INHERIT} 输出日志；已在线则复用；缺少 backend、未构建 dist、启动器不可执行时给出
 * 可读提示；仓库根目录与 {@code website} 模块目录下都能解析工作目录。</p>
 */
class SkillFinderProcessManagerTest {

    @Test
    void createsUvicornProcessBuilderWithBackendVirtualEnvironment(@TempDir Path tempDir) throws Exception {
        Path pythonPath = tempDir.resolve(".venv").resolve("Scripts").resolve("python.exe");
        Files.createDirectories(pythonPath.getParent());
        Files.createFile(pythonPath);

        SkillFinderProcessManager manager = newManager(mockChecker(), properties(tempDir, "uv"));

        ProcessBuilder builder = manager.createProcessBuilder(tempDir.toFile());

        assertThat(builder.directory()).isEqualTo(tempDir.toFile());
        assertThat(builder.command()).startsWith(pythonPath.toFile().getAbsolutePath());
        assertThat(builder.command()).containsSubsequence(
                "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "5177");
        assertThat(builder.environment()).containsEntry("PYTHONUTF8", "1");
        assertThat(builder.environment()).containsEntry("PYTHONIOENCODING", "utf-8");
        assertThat(builder.environment()).containsEntry("PYTHONUNBUFFERED", "1");
        assertThat(builder.redirectOutput()).isEqualTo(ProcessBuilder.Redirect.INHERIT);
        assertThat(builder.redirectError()).isEqualTo(ProcessBuilder.Redirect.INHERIT);
    }

    @Test
    void fallsBackToUvRunPythonWhenVirtualEnvironmentMissing(@TempDir Path tempDir) {
        SkillFinderProcessManager manager = newManager(mockChecker(), properties(tempDir, "uv"));

        ProcessBuilder builder = manager.createProcessBuilder(tempDir.toFile());

        assertThat(builder.command()).startsWith("uv", "run", "python");
        assertThat(builder.command()).containsSubsequence("app.main:app", "--port", "5177");
    }

    @Test
    void returnsAlreadyRunningWhenHealthCheckSucceeds() {
        ServiceHealthChecker checker = mockChecker();
        when(checker.check(any(ServiceHealthDefinition.class)))
                .thenReturn(ServiceHealthResult.healthy(
                        new ServiceHealthDefinition("skill-finder", "http://127.0.0.1:5177/api/health"), 200, 5));
        SkillFinderProcessManager manager = newManager(checker, new SkillFinderProperties());

        SkillFinderStartResult result = manager.start();

        assertThat(result.getStatus()).isEqualTo(SkillFinderStartResult.STATUS_ALREADY_RUNNING);
        assertThat(result.getUrl()).isEqualTo("http://127.0.0.1:5177/");
    }

    @Test
    void failsWithReadableMessageWhenFrontendBuildIsMissing(@TempDir Path tempDir) throws Exception {
        Files.createDirectories(tempDir.resolve("backend"));
        SkillFinderProcessManager manager = newManager(mockChecker(), properties(tempDir, "uv"));

        assertThatThrownBy(manager::start)
                .isInstanceOf(SkillFinderStartException.class)
                .hasMessageContaining("前端尚未构建");
    }

    @Test
    void failsWithReadableMessageWhenBackendDirectoryIsMissing(@TempDir Path tempDir) {
        SkillFinderProcessManager manager = newManager(mockChecker(), properties(tempDir, "uv"));

        assertThatThrownBy(manager::start)
                .isInstanceOf(SkillFinderStartException.class)
                .hasMessageContaining("后端目录不存在");
    }

    @Test
    void failsWithReadableMessageWhenLauncherCannotStart(@TempDir Path tempDir) throws Exception {
        Files.createDirectories(tempDir.resolve("backend"));
        Files.createDirectories(tempDir.resolve("frontend").resolve("dist"));
        Files.createFile(tempDir.resolve("frontend").resolve("dist").resolve("index.html"));
        SkillFinderProcessManager manager = newManager(mockChecker(), properties(tempDir, "missing-launcher-for-test"));

        assertThatThrownBy(manager::start)
                .isInstanceOf(SkillFinderStartException.class)
                .hasMessageContaining("uv sync");
    }

    @Test
    void resolvesWorkDirUnderWebsiteWhenStartedFromRepositoryRoot() throws Exception {
        String originalUserDir = System.getProperty("user.dir");
        try {
            System.setProperty("user.dir", resolveRepositoryRoot().getCanonicalPath());
            SkillFinderProperties properties = new SkillFinderProperties();
            SkillFinderProcessManager manager = newManager(mockChecker(), properties);

            File directory = manager.resolveWorkDir();

            assertThat(directory).isDirectory();
            assertThat(new File(directory, "backend").isDirectory()).isTrue();
            assertThat(directory.getPath().replace('\\', '/')).endsWith("website/skill-finder");
        } finally {
            System.setProperty("user.dir", originalUserDir);
        }
    }

    @Test
    void resolvesWorkDirUnderWebsiteWhenStartedFromWebsiteDirectory() throws Exception {
        String originalUserDir = System.getProperty("user.dir");
        try {
            System.setProperty("user.dir", resolveWebsiteDir().getCanonicalPath());
            SkillFinderProperties properties = new SkillFinderProperties();
            SkillFinderProcessManager manager = newManager(mockChecker(), properties);

            File directory = manager.resolveWorkDir();

            assertThat(directory).isDirectory();
            assertThat(new File(directory, "backend").isDirectory()).isTrue();
            assertThat(directory.getPath().replace('\\', '/')).endsWith("website/skill-finder");
        } finally {
            System.setProperty("user.dir", originalUserDir);
        }
    }

    private SkillFinderProcessManager newManager(ServiceHealthChecker checker, SkillFinderProperties properties) {
        return new SkillFinderProcessManager(checker, properties);
    }

    /**
     * 造一个固定返回「不健康」的健康检查器。
     *
     * <p>避免 {@code start()} 直接走「已在线复用」的短路分支，从而真正验证启动前置校验与错误提示；
     * 也确保测试不会去请求 5177。</p>
     *
     * @return 固定返回不健康结果的 mock
     */
    private ServiceHealthChecker mockChecker() {
        ServiceHealthChecker checker = mock(ServiceHealthChecker.class);
        when(checker.check(any(ServiceHealthDefinition.class)))
                .thenReturn(ServiceHealthResult.unhealthy(
                        new ServiceHealthDefinition("skill-finder", "http://127.0.0.1:5177/api/health"),
                        null, 3, "Connection failed"));
        return checker;
    }

    /**
     * 构造指向临时目录的配置。
     *
     * <p>启动超时压到 1 秒，让「未就绪」分支不必等默认 90 秒；{@code command} 只在回退分支生效，
     * 传入不存在的命令即可模拟启动器缺失。</p>
     *
     * @param workDir 临时工作目录，用例用它模拟 {@code website/skill-finder}
     * @param command 命令配置，可为 {@code uv} 或不存在的命令
     * @return 已填好工作目录、命令与超时的配置
     */
    private SkillFinderProperties properties(Path workDir, String command) {
        SkillFinderProperties properties = new SkillFinderProperties();
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
