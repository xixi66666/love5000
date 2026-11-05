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

    private ServiceHealthChecker mockChecker() {
        ServiceHealthChecker checker = mock(ServiceHealthChecker.class);
        when(checker.check(any(ServiceHealthDefinition.class)))
                .thenReturn(ServiceHealthResult.unhealthy(
                        new ServiceHealthDefinition("lottery", "http://127.0.0.1:5179/api/health"),
                        null, 3, "Connection failed"));
        return checker;
    }

    private LotteryProperties properties(Path workDir, String command) {
        LotteryProperties properties = new LotteryProperties();
        properties.setWorkDir(workDir.toAbsolutePath().toString());
        properties.setCommand(command);
        properties.setStartupTimeoutSeconds(1);
        return properties;
    }

    private File resolveWebsiteDir() {
        File currentDir = new File(System.getProperty("user.dir"));
        if ("website".equals(currentDir.getName())) {
            return currentDir;
        }
        return new File(currentDir, "website");
    }

    private File resolveRepositoryRoot() {
        return resolveWebsiteDir().getParentFile();
    }
}
