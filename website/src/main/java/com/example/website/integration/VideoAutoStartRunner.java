package com.example.website.integration;

import com.example.website.integration.health.ServiceHealthChecker;
import com.example.website.integration.health.ServiceHealthDefinition;
import com.example.website.integration.health.ServiceHealthProperties;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

import javax.annotation.PreDestroy;
import java.io.File;
import java.io.IOException;
import java.util.List;
import java.util.concurrent.TimeUnit;

@Component
@ConditionalOnProperty(prefix = "video.auto-start", name = "enabled", havingValue = "true")
public class VideoAutoStartRunner implements ApplicationRunner {

    private static final String SERVICE_NAME = "video";

    private final ServiceHealthChecker healthChecker;

    @Value("${video.auto-start.work-dir:website/video}")
    private String workDir;

    @Value("${video.auto-start.command:python}")
    private String command;

    @Value("${video.auto-start.port:5176}")
    private int port;

    @Value("${video.auto-start.health-path:/api/health}")
    private String healthPath;

    @Value("${video.auto-start.startup-timeout-seconds:30}")
    private int startupTimeoutSeconds;

    @Value("${video.auto-start.log-to-console:true}")
    private boolean logToConsole;

    private Process process;

    VideoAutoStartRunner() {
        this(new ServiceHealthChecker(new ObjectMapper(), new ServiceHealthProperties()));
    }

    @Autowired
    public VideoAutoStartRunner(ServiceHealthChecker healthChecker) {
        this.healthChecker = healthChecker;
    }

    @Override
    public void run(ApplicationArguments args) throws Exception {
        String healthUrl = buildHealthUrl();
        if (isHealthy(healthUrl)) {
            System.out.println("video is already running: " + healthUrl);
            if (logToConsole) {
                System.out.println("video logs are only attached to this IDEA console when website starts the video process. "
                        + "Stop the existing process on port " + port + " and restart website if you need live video logs here.");
            }
            return;
        }

        File directory = resolveWorkDir();
        if (!directory.exists() || !directory.isDirectory()) {
            throw new IllegalStateException("video directory does not exist: " + directory.getAbsolutePath());
        }

        try {
            ProcessBuilder builder = createProcessBuilder(directory);
            process = builder.start();
            System.out.println("video started, pid=" + getPid(process) + ", health=" + healthUrl);

            if (!waitUntilHealthy(healthUrl)) {
                warnAutoStartSkipped("health check failed after startup: " + healthUrl, null);
            }
        } catch (IOException e) {
            warnAutoStartSkipped("failed to start command '" + command + "' in " + directory.getAbsolutePath(), e);
        }
    }

    @PreDestroy
    public void stopVideo() {
        if (process != null && process.isAlive()) {
            process.destroy();
            try {
                if (!process.waitFor(5, TimeUnit.SECONDS)) {
                    process.destroyForcibly();
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                process.destroyForcibly();
            }
        }
    }

    File resolveWorkDir() throws IOException {
        File configured = new File(workDir);
        if (configured.isAbsolute()) {
            return configured.getCanonicalFile();
        }

        File currentDir = new File(System.getProperty("user.dir")).getCanonicalFile();
        File fromCurrentDir = new File(currentDir, workDir);
        if (fromCurrentDir.exists()) {
            return fromCurrentDir.getCanonicalFile();
        }

        File fromWebsiteModuleDir = resolveFromWebsiteModuleDir(currentDir);
        if (fromWebsiteModuleDir != null && fromWebsiteModuleDir.exists()) {
            return fromWebsiteModuleDir.getCanonicalFile();
        }

        File parentDir = currentDir.getParentFile();
        if (parentDir == null) {
            return fromCurrentDir.getCanonicalFile();
        }

        File fromParentDir = new File(parentDir, workDir);
        return fromParentDir.getCanonicalFile();
    }

    private File resolveFromWebsiteModuleDir(File currentDir) {
        if (!"website".equals(currentDir.getName())) {
            return null;
        }

        String normalizedWorkDir = workDir.replace('\\', '/');
        if (!normalizedWorkDir.startsWith("website/")) {
            return null;
        }

        return new File(currentDir, normalizedWorkDir.substring("website/".length()));
    }

    String buildHealthUrl() {
        return healthChecker.buildLocalUrl(port, healthPath);
    }

    ProcessBuilder createProcessBuilder(File directory) {
        List<String> commandParts = PythonCommandResolver.resolve(command, directory);
        commandParts.add("web_server.py");
        commandParts.add("--host");
        commandParts.add("127.0.0.1");
        commandParts.add("--port");
        commandParts.add(String.valueOf(port));

        ProcessBuilder builder = new ProcessBuilder(commandParts);
        builder.directory(directory);
        builder.environment().put("PYTHONUNBUFFERED", "1");
        configureLogging(builder, directory);
        return builder;
    }

    private void configureLogging(ProcessBuilder builder, File directory) {
        if (logToConsole) {
            builder.inheritIO();
            return;
        }

        File outputLog = new File(directory, "server.out.log");
        File errorLog = new File(directory, "server.err.log");
        builder.redirectOutput(ProcessBuilder.Redirect.appendTo(outputLog));
        builder.redirectError(ProcessBuilder.Redirect.appendTo(errorLog));
    }

    private boolean waitUntilHealthy(String healthUrl) {
        return healthChecker.waitUntilHealthy(
                new ServiceHealthDefinition(SERVICE_NAME, healthUrl), startupTimeoutSeconds);
    }

    boolean isHealthy(String healthUrl) {
        return healthChecker.check(new ServiceHealthDefinition(SERVICE_NAME, healthUrl)).isHealthy();
    }

    private String getPid(Process startedProcess) {
        try {
            return String.valueOf(startedProcess.getClass().getMethod("pid").invoke(startedProcess));
        } catch (Exception e) {
            return "unknown";
        }
    }

    private void warnAutoStartSkipped(String reason, Exception cause) {
        String message = "video auto-start skipped: " + reason
                + ". Start it manually or configure video.auto-start.command / website/video/.venv.";
        if (cause == null) {
            System.err.println(message);
            return;
        }
        System.err.println(message + " Cause: " + cause.getMessage());
    }
}
