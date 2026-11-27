package com.example.website.integration.personalagent;

import com.example.website.integration.health.ServiceHealthProperties;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.ByteArrayInputStream;
import java.io.IOException;
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

/**
 * {@link PersonalAgentProcessManager} 的单元测试。
 *
 * <p>被测对象负责定位 personal-agent 的 jar、拼 {@code java -jar} 命令、探测健康，并决定
 * 「复用 / 启动 / 报错」。本类不启动 JVM、不监听 5178：用 {@code Mockito.spy} 包住真实实例，
 * 只替换 {@code launch}、{@code openHealthConnection}、{@code isPortInUse} 等出口，
 * 命令拼装与启动状态机仍走真实代码。</p>
 *
 * <p>固定的关键行为：</p>
 * <ul>
 *   <li>只认「2xx + service=personal-agent + 布尔 success=true」；响应缺 service、非 2xx、
 *       非 JSON 或读取超时都判为被其他应用占用（{@code OCCUPIED}）；</li>
 *   <li>端口无人监听（{@code UNAVAILABLE}）才启动；被其他应用占用或已有实例未就绪时拒绝启动，
 *       且不去停止占用者；</li>
 *   <li>启动失败与超时只给可读提示，不暴露原始异常；超时不杀进程，下次点击复用同一进程；</li>
 *   <li>并发点击只拉起一个进程，后到的请求返回 {@code already-running}；</li>
 *   <li>仓库根目录与 {@code website} 模块目录下都能解析工作目录。</li>
 * </ul>
 */
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
    void treatsInvalidResponseAndReadTimeoutAsOccupiedButUnreachablePortAsOffline(@TempDir Path directory)
            throws Exception {
        PersonalAgentProcessManager manager = manager(directory, "java");
        healthConnection(manager, 200, "not JSON");
        assertThat(manager.probeHealth()).isEqualTo(OCCUPIED);
        HttpURLConnection connection = mock(HttpURLConnection.class);
        doReturn(connection).when(manager).openHealthConnection();
        when(connection.getResponseCode()).thenThrow(new SocketTimeoutException());
        assertThat(manager.probeHealth()).isEqualTo(OCCUPIED);

        doReturn(false).when(manager).isPortInUse();
        HttpURLConnection unreachable = mock(HttpURLConnection.class);
        doReturn(unreachable).when(manager).openHealthConnection();
        assertThat(manager.probeHealth()).isEqualTo(UNAVAILABLE);
        verify(unreachable, never()).getResponseCode();
    }

    @Test
    void startsWhenNothingListensEvenIfHealthProbeTimesOut(@TempDir Path directory) throws Exception {
        createEntry(directory);
        PersonalAgentProcessManager manager = manager(directory, "java");
        doReturn(UNAVAILABLE).when(manager).probeHealth();
        doReturn(false).when(manager).isPortInUse();
        Process process = mock(Process.class);
        when(process.isAlive()).thenReturn(true);
        doReturn(process).when(manager).launch(any(ProcessBuilder.class));
        doReturn(true).when(manager).waitUntilHealthy();

        assertThat(manager.start().getStatus()).isEqualTo("started");
        verify(manager, times(1)).launch(any(ProcessBuilder.class));
    }

    @Test
    void reusesOnlyMatchingHealthyServiceWithoutLaunching(@TempDir Path directory) throws Exception {
        PersonalAgentProcessManager manager = manager(directory, "java");
        healthConnection(manager, 200, "{\"success\":true,\"service\":\"personal-agent\"}");

        PersonalAgentStartResult result = manager.start();

        assertThat(result.getStatus()).isEqualTo("already-running");
        assertThat(result.getUrl()).isEqualTo("http://127.0.0.1:5178/");
        verify(manager, never()).launch(any(ProcessBuilder.class));
    }

    @Test
    void rejectsOtherHealthyServiceWithoutLaunchingOrStoppingIt(@TempDir Path directory) throws Exception {
        PersonalAgentProcessManager manager = manager(directory, "java");
        healthConnection(manager, 200, "{\"success\":true,\"service\":\"other-app\"}");

        assertThatThrownBy(manager::start).isInstanceOf(PersonalAgentStartException.class)
                .hasMessageContaining("端口 5178").hasMessageContaining("占用");
        verify(manager, never()).launch(any(ProcessBuilder.class));
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

    /**
     * 造一个「端口空闲且健康探测不可用」的实例，让 {@code start()} 直接进入启动分支。
     *
     * @param directory 冒充 personal-agent 模块根目录
     * @return 已固定 {@code probeHealth} 与 {@code isPortInUse} 结果的 spy
     */
    private PersonalAgentProcessManager offlineManager(Path directory) {
        PersonalAgentProcessManager manager = manager(directory, "java");
        doReturn(UNAVAILABLE).when(manager).probeHealth();
        doReturn(false).when(manager).isPortInUse();
        return manager;
    }

    /**
     * 用 {@code Mockito.spy} 包住真实实例。
     *
     * <p>命令拼装与启动状态机仍走真实代码，只在用例里替换 {@code launch}、探测等出口，
     * 这样既验证真实逻辑，又不会真的拉起 JVM 或连接 5178。</p>
     *
     * @param directory 冒充 personal-agent 模块根目录
     * @param command   Java 命令
     * @return 可替换部分方法的 spy
     */
    private PersonalAgentProcessManager manager(Path directory, String command) {
        return spy(new PersonalAgentProcessManager(new ObjectMapper(), new ServiceHealthProperties(),
                properties(directory, command)));
    }

    /**
     * 构造指向临时目录的配置。
     *
     * <p>工作目录固定为临时目录，避免误碰仓库里真实的 personal-agent 产物；命令由用例指定，
     * 传空串即可覆盖「回退到当前 JVM 的 java」这条分支。</p>
     *
     * @param directory 冒充 personal-agent 模块根目录
     * @param command   Java 命令，空串表示回退到当前 JVM 的 {@code bin/java}
     * @return 已填好工作目录与命令的配置
     */
    private PersonalAgentProperties properties(Path directory, String command) {
        PersonalAgentProperties properties = new PersonalAgentProperties();
        properties.setWorkDir(directory.toAbsolutePath().toString());
        properties.setCommand(command);
        return properties;
    }

    /**
     * 预置 Maven 产物的占位文件。
     *
     * <p>启动前的 jar 存在性校验必须先通过，用例才能走到「拉起进程」；这里只建空文件，
     * 不触发任何真实构建。</p>
     *
     * @param directory 冒充 personal-agent 模块根目录
     * @throws IOException 临时目录无法写入
     */
    private void createEntry(Path directory) throws IOException {
        Files.createDirectories(directory.resolve("target"));
        Files.createFile(directory.resolve("target/personal-agent-0.0.1-SNAPSHOT.jar"));
    }

    /**
     * 伪造一次健康探测。
     *
     * <p>同时声明端口在监听，并按状态码选择 {@code getInputStream()} 或
     * {@code getErrorStream()}，让被测代码用同一套解析逻辑读到给定响应体。</p>
     *
     * @param manager 被测实例，其 {@code openHealthConnection()} 被替换
     * @param status  HTTP 状态码
     * @param body    响应体，可以故意写成非法 JSON 以覆盖解析失败分支
     * @return 可继续设置异常行为的 mock 连接
     */
    private HttpURLConnection healthConnection(PersonalAgentProcessManager manager, int status, String body)
            throws Exception {
        doReturn(true).when(manager).isPortInUse();
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
