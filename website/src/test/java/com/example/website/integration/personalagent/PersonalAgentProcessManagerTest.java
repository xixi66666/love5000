package com.example.website.integration.personalagent;

import com.example.website.integration.health.ServiceHealthProperties;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.net.ConnectException;
import java.net.HttpURLConnection;
import java.net.SocketTimeoutException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

import static com.example.website.integration.personalagent.PersonalAgentProcessManager.HealthStatus.*;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

class PersonalAgentProcessManagerTest {

    @Test
    void createsLoopbackJavaCommandUsingPrebuiltJar(@TempDir Path directory) {
        PersonalAgentProcessManager manager = manager(directory, "C:/Java With Spaces/bin/java.exe");

        ProcessBuilder builder = manager.createProcessBuilder(directory.toFile());

        assertThat(builder.directory()).isEqualTo(directory.toFile());
        assertThat(builder.command()).containsExactly("C:/Java With Spaces/bin/java.exe", "-jar",
                directory.resolve("target/personal-agent-0.0.1-SNAPSHOT.jar").toFile().getAbsolutePath(),
                "--server.address=127.0.0.1", "--server.port=5178");
        assertThat(builder.redirectOutput()).isEqualTo(ProcessBuilder.Redirect.INHERIT);
        assertThat(builder.redirectError()).isEqualTo(ProcessBuilder.Redirect.INHERIT);
    }

    @Test
    void defaultsToJavaHomeAndNeverRunsBuildCommands(@TempDir Path directory) {
        String executable = System.getProperty("java.home") + java.io.File.separator + "bin"
                + java.io.File.separator + (java.io.File.separatorChar == '\\' ? "java.exe" : "java");
        assertThat(manager(directory, "").createProcessBuilder(directory.toFile()).command())
                .startsWith(executable, "-jar")
                .doesNotContain("mvn", "cmd", "powershell");
    }

    @Test
    void supportsConfiguredJavaCommandAndLogFiles(@TempDir Path directory) {
        PersonalAgentProperties properties = properties(directory, "java");
        properties.setLogToConsole(false);
        PersonalAgentProcessManager manager = new PersonalAgentProcessManager(
                new ObjectMapper(), new ServiceHealthProperties(), properties);

        ProcessBuilder builder = manager.createProcessBuilder(directory.toFile());

        assertThat(builder.command()).startsWith("java", "-jar");
        assertThat(builder.redirectOutput().file()).isEqualTo(directory.resolve("server.out.log").toFile());
        assertThat(builder.redirectError().file()).isEqualTo(directory.resolve("server.err.log").toFile());
    }

    @Test
    void requiresBooleanSuccessAndExactServiceIdentity(@TempDir Path directory) throws Exception {
        PersonalAgentProcessManager manager = manager(directory, "java");
        HttpURLConnection connection = healthConnection(manager, 200,
                "{\"success\":true,\"service\":\"personal-agent\"}");
        assertThat(manager.probeHealth()).isEqualTo(HEALTHY);
        verify(connection).setConnectTimeout(2000);
        verify(connection).setReadTimeout(3000);
        verify(connection).setInstanceFollowRedirects(false);
        verify(connection).disconnect();

        healthConnection(manager, 200, "{\"success\":true,\"service\":\"other-app\"}");
        assertThat(manager.probeHealth()).isEqualTo(OCCUPIED);
        healthConnection(manager, 200, "{\"success\":true}");
        assertThat(manager.probeHealth()).isEqualTo(OCCUPIED);
        healthConnection(manager, 200, "{\"success\":\"true\",\"service\":\"personal-agent\"}");
        assertThat(manager.probeHealth()).isEqualTo(NOT_READY);
        healthConnection(manager, 503, "{\"success\":false,\"service\":\"personal-agent\"}");
        assertThat(manager.probeHealth()).isEqualTo(NOT_READY);
    }

    @Test
    void treatsInvalidResponseAndTimeoutAsOccupiedButRefusedConnectionAsOffline(@TempDir Path directory)
            throws Exception {
        PersonalAgentProcessManager manager = manager(directory, "java");
        healthConnection(manager, 200, "not JSON");
        assertThat(manager.probeHealth()).isEqualTo(OCCUPIED);
        HttpURLConnection connection = mock(HttpURLConnection.class);
        doReturn(connection).when(manager).openHealthConnection();
        when(connection.getResponseCode()).thenThrow(new SocketTimeoutException(), new ConnectException());
        assertThat(manager.probeHealth()).isEqualTo(OCCUPIED);
        assertThat(manager.probeHealth()).isEqualTo(UNAVAILABLE);
    }

    @Test
    void reusesOnlyMatchingHealthyServiceWithoutLaunching(@TempDir Path directory) throws Exception {
        PersonalAgentProcessManager manager = manager(directory, "java");
        healthConnection(manager, 200, "{\"success\":true,\"service\":\"personal-agent\"}");

        PersonalAgentStartResult result = manager.start();

        assertThat(result.getStatus()).isEqualTo("already-running");
        assertThat(result.getUrl()).isEqualTo("http://127.0.0.1:5178/");
        verify(manager, never()).launch(any(ProcessBuilder.class));
        verify(manager, never()).isPortInUse();
    }

    @Test
    void rejectsOtherHealthyServiceWithoutLaunchingOrStoppingIt(@TempDir Path directory) throws Exception {
        PersonalAgentProcessManager manager = manager(directory, "java");
        healthConnection(manager, 200, "{\"success\":true,\"service\":\"other-app\"}");

        assertThatThrownBy(manager::start).isInstanceOf(PersonalAgentStartException.class)
                .hasMessageContaining("端口 5178").hasMessageContaining("占用");
        verify(manager, never()).launch(any(ProcessBuilder.class));
        verify(manager, never()).isPortInUse();
    }

    @Test
    void rejectsNonHttpPortOccupantAndUnhealthyExistingInstance(@TempDir Path directory) throws Exception {
        PersonalAgentProcessManager manager = offlineManager(directory);
        doReturn(true).when(manager).isPortInUse();
        assertThatThrownBy(manager::start).hasMessageContaining("占用");
        verify(manager, never()).launch(any(ProcessBuilder.class));

        doReturn(NOT_READY).when(manager).probeHealth();
        assertThatThrownBy(manager::start).hasMessageContaining("尚未就绪");
        verify(manager, never()).launch(any(ProcessBuilder.class));
    }

    @Test
    void reportsMissingEntryAndLauncherWithoutRawExceptions(@TempDir Path directory) throws Exception {
        PersonalAgentProcessManager manager = offlineManager(directory);
        assertThatThrownBy(manager::start).hasMessageContaining("mvn -pl personal-agent -am package");
        createEntry(directory);
        doThrow(new IOException("sensitive detail omitted")).when(manager).launch(any(ProcessBuilder.class));
        assertThatThrownBy(manager::start).hasMessageContaining("Java")
                .hasMessageNotContaining("sensitive detail omitted");
    }

    @Test
    void startupTimeoutDoesNotKillProcessOrLaunchDuplicateOnRetry(@TempDir Path directory) throws Exception {
        createEntry(directory);
        PersonalAgentProcessManager manager = offlineManager(directory);
        Process process = mock(Process.class);
        when(process.isAlive()).thenReturn(true);
        doReturn(process).when(manager).launch(any(ProcessBuilder.class));
        doReturn(false, true).when(manager).waitUntilHealthy();

        assertThatThrownBy(manager::start).hasMessageContaining("90 秒");
        assertThat(manager.start().getStatus()).isEqualTo("already-running");

        verify(manager, times(1)).launch(any(ProcessBuilder.class));
        verify(process, never()).destroy();
        verify(process, never()).destroyForcibly();
    }

    @Test
    void concurrentStartsShareOneProcess(@TempDir Path directory) throws Exception {
        createEntry(directory);
        PersonalAgentProcessManager manager = offlineManager(directory);
        Process process = mock(Process.class);
        when(process.isAlive()).thenReturn(true);
        doReturn(process).when(manager).launch(any(ProcessBuilder.class));
        CountDownLatch waiting = new CountDownLatch(1);
        CountDownLatch release = new CountDownLatch(1);
        AtomicBoolean ready = new AtomicBoolean();
        doAnswer(invocation -> ready.get() ? HEALTHY : UNAVAILABLE).when(manager).probeHealth();
        doAnswer(invocation -> {
            waiting.countDown();
            if (!release.await(5, TimeUnit.SECONDS)) {
                throw new AssertionError("Test startup was not released");
            }
            ready.set(true);
            return true;
        }).when(manager).waitUntilHealthy();
        ExecutorService executor = Executors.newFixedThreadPool(2);
        try {
            CompletableFuture<PersonalAgentStartResult> first = CompletableFuture.supplyAsync(manager::start, executor);
            assertThat(waiting.await(5, TimeUnit.SECONDS)).isTrue();
            CompletableFuture<PersonalAgentStartResult> second = CompletableFuture.supplyAsync(manager::start, executor);
            release.countDown();
            assertThat(first.get(5, TimeUnit.SECONDS).getStatus()).isEqualTo("started");
            assertThat(second.get(5, TimeUnit.SECONDS).getStatus()).isEqualTo("already-running");
            verify(manager, times(1)).launch(any(ProcessBuilder.class));
        } finally {
            release.countDown();
            executor.shutdownNow();
        }
    }

    @Test
    void resolvesWorkDirectoryFromRootAndWebsite(@TempDir Path root) throws Exception {
        Path directory = Files.createDirectories(root.resolve("personal-agent"));
        Files.createDirectories(root.resolve("website"));
        String original = System.getProperty("user.dir");
        try {
            PersonalAgentProcessManager manager = new PersonalAgentProcessManager(
                    new ObjectMapper(), new ServiceHealthProperties(), new PersonalAgentProperties());
            System.setProperty("user.dir", root.toString());
            assertThat(manager.resolveWorkDir()).isEqualTo(directory.toFile().getCanonicalFile());
            System.setProperty("user.dir", root.resolve("website").toString());
            assertThat(manager.resolveWorkDir()).isEqualTo(directory.toFile().getCanonicalFile());
        } finally {
            System.setProperty("user.dir", original);
        }
    }

    private PersonalAgentProcessManager offlineManager(Path directory) {
        PersonalAgentProcessManager manager = manager(directory, "java");
        doReturn(UNAVAILABLE).when(manager).probeHealth();
        doReturn(false).when(manager).isPortInUse();
        return manager;
    }

    private PersonalAgentProcessManager manager(Path directory, String command) {
        return spy(new PersonalAgentProcessManager(new ObjectMapper(), new ServiceHealthProperties(),
                properties(directory, command)));
    }

    private PersonalAgentProperties properties(Path directory, String command) {
        PersonalAgentProperties properties = new PersonalAgentProperties();
        properties.setWorkDir(directory.toAbsolutePath().toString());
        properties.setCommand(command);
        return properties;
    }

    private void createEntry(Path directory) throws IOException {
        Files.createDirectories(directory.resolve("target"));
        Files.createFile(directory.resolve("target/personal-agent-0.0.1-SNAPSHOT.jar"));
    }

    private HttpURLConnection healthConnection(PersonalAgentProcessManager manager, int status, String body)
            throws Exception {
        HttpURLConnection connection = mock(HttpURLConnection.class);
        when(connection.getResponseCode()).thenReturn(status);
        ByteArrayInputStream input = new ByteArrayInputStream(body.getBytes(StandardCharsets.UTF_8));
        if (status >= 200 && status < 300) {
            when(connection.getInputStream()).thenReturn(input);
        } else {
            when(connection.getErrorStream()).thenReturn(input);
        }
        doReturn(connection).when(manager).openHealthConnection();
        return connection;
    }
}
