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

    private ServiceHealthChecker mockChecker() {
        ServiceHealthChecker checker = mock(ServiceHealthChecker.class);
        when(checker.check(any(ServiceHealthDefinition.class)))
                .thenReturn(ServiceHealthResult.unhealthy(
                        new ServiceHealthDefinition("skill-finder", "http://127.0.0.1:5177/api/health"),
                        null, 3, "Connection failed"));
        return checker;
    }

    private SkillFinderProperties properties(Path workDir, String command) {
        SkillFinderProperties properties = new SkillFinderProperties();
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
