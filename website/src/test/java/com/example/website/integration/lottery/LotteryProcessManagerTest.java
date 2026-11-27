package com.example.website.integration.lottery;

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
 * {@link LotteryProcessManager} 的单元测试。
 *
 * <p>被测对象只在首页卡片点击时拉起 {@code website/lottery}
 * （{@code python server.py --port 5179}）。本类不启动 Python、不连真实端口：健康检查由
 * mock 的 {@link ServiceHealthChecker} 固定为不健康，让 {@code start()} 走启动分支；
 * 工作目录用 {@link TempDir}，启动超时压到 1 秒，避免等待默认的 60 秒。</p>
 *
 * <p>固定的关键分支：命令与 UTF-8 环境变量、已在线则复用、缺少 {@code server.py}、
 * 解释器不可执行时的可读提示，以及从仓库根目录和 {@code website} 模块目录都能解析工作目录。</p>
 */
class LotteryProcessManagerTest {

    @Test
    void createsPythonProcessBuilderForServerScript(@TempDir Path tempDir) {
        LotteryProcessManager manager = new LotteryProcessManager(mockChecker(), properties(tempDir, "python"));

        ProcessBuilder builder = manager.createProcessBuilder(tempDir.toFile());

        assertThat(builder.directory()).isEqualTo(tempDir.toFile());
        assertThat(builder.command()).startsWith("python", "server.py", "--port", "5179");
        assertThat(builder.environment()).containsEntry("PYTHONUTF8", "1");
        assertThat(builder.environment()).containsEntry("PYTHONIOENCODING", "utf-8");
        assertThat(builder.environment()).containsEntry("PYTHONUNBUFFERED", "1");
        assertThat(builder.environment()).containsEntry("LOTTERY_PORT", "5179");
        assertThat(builder.redirectOutput()).isEqualTo(ProcessBuilder.Redirect.INHERIT);
        assertThat(builder.redirectError()).isEqualTo(ProcessBuilder.Redirect.INHERIT);
    }

    @Test
    void returnsAlreadyRunningWhenHealthCheckSucceeds() {
        ServiceHealthChecker checker = mockChecker();
        when(checker.check(any(ServiceHealthDefinition.class)))
                .thenReturn(ServiceHealthResult.healthy(
                        new ServiceHealthDefinition("lottery", "http://127.0.0.1:5179/api/health"), 200, 5));
        LotteryProcessManager manager = new LotteryProcessManager(checker, new LotteryProperties());

        LotteryStartResult result = manager.start();

        assertThat(result.getStatus()).isEqualTo(LotteryStartResult.STATUS_ALREADY_RUNNING);
        assertThat(result.getUrl()).isEqualTo("http://127.0.0.1:5179/");
    }

    @Test
    void failsWithReadableMessageWhenServerScriptIsMissing(@TempDir Path tempDir) {
        LotteryProcessManager manager = new LotteryProcessManager(mockChecker(), properties(tempDir, "python"));

        assertThatThrownBy(manager::start)
                .isInstanceOf(LotteryStartException.class)
                .hasMessageContaining("server.py");
    }

    @Test
    void failsWithReadableMessageWhenLauncherCannotStart(@TempDir Path tempDir) throws Exception {
        // 启动失败要指向可执行的修复动作（安装 numpy / pandas / requests），不能把原始
        // IOException 直接抛给页面。
        Files.createFile(tempDir.resolve("server.py"));
        LotteryProcessManager manager = new LotteryProcessManager(
                mockChecker(), properties(tempDir, "missing-launcher-for-test"));

        assertThatThrownBy(manager::start)
                .isInstanceOf(LotteryStartException.class)
                .hasMessageContaining("numpy");
    }

    @Test
    void resolvesWorkDirUnderWebsiteWhenStartedFromRepositoryRoot() throws Exception {
        String originalUserDir = System.getProperty("user.dir");
        try {
            System.setProperty("user.dir", resolveRepositoryRoot().getCanonicalPath());
            LotteryProcessManager manager = new LotteryProcessManager(mockChecker(), new LotteryProperties());

            File directory = manager.resolveWorkDir();

            assertThat(directory).isDirectory();
            assertThat(new File(directory, "server.py").isFile()).isTrue();
            assertThat(directory.getPath().replace('\\', '/')).endsWith("website/lottery");
        } finally {
            System.setProperty("user.dir", originalUserDir);
        }
    }

    @Test
    void resolvesWorkDirUnderWebsiteWhenStartedFromWebsiteDirectory() throws Exception {
        String originalUserDir = System.getProperty("user.dir");
        try {
            System.setProperty("user.dir", resolveWebsiteDir().getCanonicalPath());
            LotteryProcessManager manager = new LotteryProcessManager(mockChecker(), new LotteryProperties());

            File directory = manager.resolveWorkDir();

            assertThat(directory).isDirectory();
            assertThat(new File(directory, "server.py").isFile()).isTrue();
            assertThat(directory.getPath().replace('\\', '/')).endsWith("website/lottery");
        } finally {
            System.setProperty("user.dir", originalUserDir);
        }
    }

    /**
     * 造一个永远判定「不健康」的健康检查器。
     *
     * <p>这样 {@code start()} 不会走「已有实例直接复用」的短路分支，才能验证进程参数与失败提示；
     * 同时也确保测试不会真的去请求 5179。</p>
     *
     * @return 固定返回不健康结果的 mock
     */
    private ServiceHealthChecker mockChecker() {
        ServiceHealthChecker checker = mock(ServiceHealthChecker.class);
        when(checker.check(any(ServiceHealthDefinition.class)))
                .thenReturn(ServiceHealthResult.unhealthy(
                        new ServiceHealthDefinition("lottery", "http://127.0.0.1:5179/api/health"),
                        null, 3, "Connection failed"));
        return checker;
    }

    /**
     * 构造指向临时目录的配置。
     *
     * <p>启动超时压到 1 秒，让「服务未就绪」分支不必等默认 60 秒；命令由用例指定，
     * 传入不存在的命令即可模拟解释器缺失。</p>
     *
     * @param workDir 临时工作目录，通常不含 {@code server.py}
     * @param command 子进程命令，例如 {@code python} 或不存在的命令
     * @return 已填好工作目录、命令与超时的配置
     */
    private LotteryProperties properties(Path workDir, String command) {
        LotteryProperties properties = new LotteryProperties();
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
        return resolveWebsiteDir().getParentFile();
    }
}
