package com.example.website.integration.personalagent;

import com.example.website.integration.health.ServiceHealthProperties;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.net.ConnectException;
import java.net.HttpURLConnection;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.URL;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;

@Component
@ConditionalOnProperty(prefix = "personal-agent.click-start", name = "enabled", havingValue = "true")
public class PersonalAgentProcessManager {

    enum HealthStatus { HEALTHY, UNAVAILABLE, NOT_READY, OCCUPIED }

    private final ObjectMapper objectMapper;
    private final ServiceHealthProperties healthProperties;
    private final PersonalAgentProperties properties;
    private Process process;

    public PersonalAgentProcessManager(ObjectMapper objectMapper, ServiceHealthProperties healthProperties,
                                       PersonalAgentProperties properties) {
        this.objectMapper = objectMapper;
        this.healthProperties = healthProperties;
        this.properties = properties;
    }

    public synchronized PersonalAgentStartResult start() {
        HealthStatus health = probeHealth();
        if (health == HealthStatus.HEALTHY) {
            return result(PersonalAgentStartResult.STATUS_ALREADY_RUNNING);
        }
        if (health == HealthStatus.OCCUPIED) {
            throw occupiedPort();
        }
        if (process != null && process.isAlive()) {
            if (waitUntilHealthy()) {
                return result(PersonalAgentStartResult.STATUS_ALREADY_RUNNING);
            }
            throw notReady();
        }
        if (health == HealthStatus.NOT_READY || isPortInUse()) {
            throw occupiedPort();
        }

        File workDir;
        try {
            workDir = resolveWorkDir();
        } catch (IOException exception) {
            throw new PersonalAgentStartException("个人 Agent 工作目录解析失败，请检查 personal-agent.click-start.work-dir");
        }
        if (!jarFile(workDir).isFile()) {
            throw new PersonalAgentStartException("个人 Agent 尚未构建，请先在仓库根目录执行 "
                    + "mvn -pl personal-agent -am package -DskipTests");
        }

        try {
            process = launch(createProcessBuilder(workDir));
        } catch (IOException exception) {
            throw new PersonalAgentStartException("个人 Agent 启动失败，请检查 Java 运行环境或 "
                    + "PERSONAL_AGENT_COMMAND 指定的 Java 可执行文件，以及 Maven 构建产物");
        }
        if (!waitUntilHealthy()) {
            throw notReady();
        }
        return result(PersonalAgentStartResult.STATUS_STARTED);
    }

    public boolean isRunning() {
        return probeHealth() == HealthStatus.HEALTHY;
    }

    public String appUrl() {
        return "http://127.0.0.1:" + properties.getPort() + "/";
    }

    String buildHealthUrl() {
        String path = properties.getHealthPath();
        return appUrl() + (path.startsWith("/") ? path.substring(1) : path);
    }

    File resolveWorkDir() throws IOException {
        String configuredPath = properties.getWorkDir();
        File configured = new File(configuredPath);
        if (configured.isAbsolute()) {
            return configured.getCanonicalFile();
        }
        File currentDir = new File(System.getProperty("user.dir")).getCanonicalFile();
        File fromCurrent = new File(currentDir, configuredPath);
        if (fromCurrent.exists()) {
            return fromCurrent.getCanonicalFile();
        }
        File parent = currentDir.getParentFile();
        return parent == null ? fromCurrent.getCanonicalFile()
                : new File(parent, configuredPath).getCanonicalFile();
    }

    ProcessBuilder createProcessBuilder(File workDir) {
        List<String> command = new ArrayList<>();
        command.add(resolveJavaCommand());
        command.add("-jar");
        command.add(jarFile(workDir).getAbsolutePath());
        command.add("--server.address=127.0.0.1");
        command.add("--server.port=" + properties.getPort());
        ProcessBuilder builder = new ProcessBuilder(command);
        builder.directory(workDir);
        if (properties.isLogToConsole()) {
            builder.inheritIO();
        } else {
            builder.redirectOutput(ProcessBuilder.Redirect.appendTo(new File(workDir, "server.out.log")));
            builder.redirectError(ProcessBuilder.Redirect.appendTo(new File(workDir, "server.err.log")));
        }
        return builder;
    }

    private String resolveJavaCommand() {
        String configured = properties.getCommand();
        if (configured != null && !configured.trim().isEmpty()) {
            return configured;
        }
        File executable = new File(System.getProperty("java.home"),
                "bin" + File.separator + (File.separatorChar == '\\' ? "java.exe" : "java"));
        return executable.getAbsolutePath();
    }

    private File jarFile(File workDir) {
        return new File(workDir, "target" + File.separator + "personal-agent-0.0.1-SNAPSHOT.jar");
    }

    Process launch(ProcessBuilder builder) throws IOException {
        return builder.start();
    }

    HttpURLConnection openHealthConnection() throws IOException {
        return (HttpURLConnection) new URL(buildHealthUrl()).openConnection();
    }

    HealthStatus probeHealth() {
        HttpURLConnection connection = null;
        try {
            connection = openHealthConnection();
            connection.setRequestMethod("GET");
            connection.setConnectTimeout(healthProperties.getConnectTimeoutMs());
            connection.setReadTimeout(healthProperties.getReadTimeoutMs());
            connection.setUseCaches(false);
            connection.setInstanceFollowRedirects(false);
            int status = connection.getResponseCode();
            try (InputStream input = status >= 200 && status < 300
                    ? connection.getInputStream() : connection.getErrorStream()) {
                if (input == null) {
                    return HealthStatus.OCCUPIED;
                }
                JsonNode body = objectMapper.readTree(input);
                if (body == null || !"personal-agent".equals(body.path("service").asText())) {
                    return HealthStatus.OCCUPIED;
                }
                JsonNode success = body.path("success");
                return status >= 200 && status < 300 && success.isBoolean() && success.booleanValue()
                        ? HealthStatus.HEALTHY : HealthStatus.NOT_READY;
            }
        } catch (ConnectException exception) {
            return HealthStatus.UNAVAILABLE;
        } catch (IOException exception) {
            return HealthStatus.OCCUPIED;
        } finally {
            if (connection != null) {
                connection.disconnect();
            }
        }
    }

    boolean isPortInUse() {
        try (Socket socket = new Socket()) {
            socket.connect(new InetSocketAddress("127.0.0.1", properties.getPort()),
                    healthProperties.getConnectTimeoutMs());
            return true;
        } catch (ConnectException exception) {
            return false;
        } catch (IOException exception) {
            return true;
        }
    }

    boolean waitUntilHealthy() {
        long timeout = TimeUnit.SECONDS.toNanos(Math.max(1, properties.getStartupTimeoutSeconds()));
        long startedAt = System.nanoTime();
        do {
            HealthStatus health = probeHealth();
            if (health == HealthStatus.HEALTHY) {
                return true;
            }
            if (health == HealthStatus.OCCUPIED) {
                throw occupiedPort();
            }
            if (process != null && !process.isAlive()) {
                return false;
            }
            if (System.nanoTime() - startedAt >= timeout) {
                break;
            }
            try {
                Thread.sleep(250L);
            } catch (InterruptedException exception) {
                Thread.currentThread().interrupt();
                return false;
            }
        } while (System.nanoTime() - startedAt < timeout);
        return false;
    }

    private PersonalAgentStartResult result(String status) {
        return new PersonalAgentStartResult(status, appUrl());
    }

    private PersonalAgentStartException occupiedPort() {
        return new PersonalAgentStartException("个人 Agent 端口 " + properties.getPort()
                + " 已被占用或已有实例尚未就绪，请检查该端口；未启动或停止其他应用");
    }

    private PersonalAgentStartException notReady() {
        return new PersonalAgentStartException("个人 Agent 在 " + properties.getStartupTimeoutSeconds()
                + " 秒内未就绪，请检查服务日志；再次点击会复用仍在启动的进程");
    }
}
