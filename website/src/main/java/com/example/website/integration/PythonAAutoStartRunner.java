package com.example.website.integration;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

import javax.annotation.PreDestroy;
import java.io.File;
import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.TimeUnit;

@Component
@ConditionalOnProperty(prefix = "python-a.auto-start", name = "enabled", havingValue = "true")
public class PythonAAutoStartRunner implements ApplicationRunner {

    @Value("${python-a.auto-start.work-dir:python-a}")
    private String workDir;

    @Value("${python-a.auto-start.command:python}")
    private String command;

    @Value("${python-a.auto-start.port:5174}")
    private int port;

    @Value("${python-a.auto-start.health-path:/api/health}")
    private String healthPath;

    @Value("${python-a.auto-start.startup-timeout-seconds:20}")
    private int startupTimeoutSeconds;

    private Process process;

    @Override
    public void run(ApplicationArguments args) throws Exception {
        String healthUrl = buildHealthUrl();
        if (isHealthy(healthUrl)) {
            System.out.println("python-a is already running: " + healthUrl);
            return;
        }

        File directory = resolveWorkDir();
        if (!directory.exists() || !directory.isDirectory()) {
            throw new IllegalStateException("python-a directory does not exist: " + directory.getAbsolutePath());
        }

        File outputLog = new File(directory, "server.out.log");
        File errorLog = new File(directory, "server.err.log");

        ProcessBuilder builder = new ProcessBuilder(command, "server.py");
        builder.directory(directory);
        builder.environment().put("PORT", String.valueOf(port));
        builder.environment().put("PYTHONUNBUFFERED", "1");
        builder.redirectOutput(ProcessBuilder.Redirect.appendTo(outputLog));
        builder.redirectError(ProcessBuilder.Redirect.appendTo(errorLog));

        process = builder.start();
        System.out.println("python-a started, pid=" + getPid(process) + ", health=" + healthUrl);

        if (!waitUntilHealthy(healthUrl)) {
            throw new IllegalStateException("python-a health check failed after startup: " + healthUrl);
        }
    }

    @PreDestroy
    public void stopPythonA() {
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

    private File resolveWorkDir() throws IOException {
        File configured = new File(workDir);
        if (configured.isAbsolute()) {
            return configured.getCanonicalFile();
        }

        File currentDir = new File(System.getProperty("user.dir"));
        File fromCurrentDir = new File(currentDir, workDir);
        if (fromCurrentDir.exists()) {
            return fromCurrentDir.getCanonicalFile();
        }

        File fromParentDir = new File(currentDir.getParentFile(), workDir);
        return fromParentDir.getCanonicalFile();
    }

    private String buildHealthUrl() {
        String normalizedPath = healthPath.startsWith("/") ? healthPath : "/" + healthPath;
        return "http://127.0.0.1:" + port + normalizedPath;
    }

    private boolean waitUntilHealthy(String healthUrl) {
        int attempts = Math.max(1, startupTimeoutSeconds);
        for (int i = 0; i < attempts; i++) {
            if (isHealthy(healthUrl)) {
                return true;
            }

            try {
                Thread.sleep(1000L);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return false;
            }
        }
        return false;
    }

    private boolean isHealthy(String healthUrl) {
        HttpURLConnection connection = null;
        try {
            URL url = new URL(healthUrl);
            connection = (HttpURLConnection) url.openConnection();
            connection.setRequestMethod("GET");
            connection.setConnectTimeout(2000);
            connection.setReadTimeout(3000);
            return connection.getResponseCode() >= 200 && connection.getResponseCode() < 300;
        } catch (IOException e) {
            return false;
        } finally {
            if (connection != null) {
                connection.disconnect();
            }
        }
    }

    private String getPid(Process startedProcess) {
        try {
            return String.valueOf(startedProcess.getClass().getMethod("pid").invoke(startedProcess));
        } catch (Exception e) {
            return "unknown";
        }
    }
}
