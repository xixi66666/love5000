package com.example.website.integration;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.test.util.ReflectionTestUtils;

import java.io.File;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;

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
