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

    private ServiceHealthChecker mockChecker() {
        ServiceHealthChecker checker = mock(ServiceHealthChecker.class);
        when(checker.check(any(ServiceHealthDefinition.class)))
                .thenReturn(ServiceHealthResult.unhealthy(
                        new ServiceHealthDefinition("scrapling-ui", "http://127.0.0.1:5176/api/health"),
                        null, 3, "Connection failed"));
        return checker;
    }

    private ScraplingUiProperties properties(Path workDir, String command) {
        ScraplingUiProperties properties = new ScraplingUiProperties();
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
        File websiteDir = resolveWebsiteDir();
        return websiteDir.getParentFile();
    }
}
