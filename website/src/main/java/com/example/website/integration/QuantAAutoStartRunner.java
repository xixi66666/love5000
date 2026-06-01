package com.example.website.integration;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

import javax.annotation.PreDestroy;
import java.io.BufferedReader;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.TimeUnit;

@Component
@ConditionalOnProperty(prefix = "quant-a.auto-start", name = "enabled", havingValue = "true")
public class QuantAAutoStartRunner implements ApplicationRunner {

    @Value("${quant-a.auto-start.work-dir:website/quant-a}")
    private String workDir;

    @Value("${quant-a.auto-start.command:python}")
    private String command;

    @Value("${quant-a.auto-start.port:5175}")
    private int port;

    @Value("${quant-a.auto-start.health-path:/api/health}")
    private String healthPath;

    @Value("${quant-a.auto-start.startup-timeout-seconds:30}")
    private int startupTimeoutSeconds;

    @Value("${quant-a.auto-start.log-to-console:true}")
    private boolean logToConsole;

    private Process process;

    @Override
    public void run(ApplicationArguments args) throws Exception {
        String healthUrl = buildHealthUrl();
        if (isHealthy(healthUrl)) {
            System.out.println("quant-a is already running: " + healthUrl);
            return;
        }

        File directory = resolveWorkDir();
        if (!directory.exists() || !directory.isDirectory()) {
            throw new IllegalStateException("quant-a directory does not exist: " + directory.getAbsolutePath());
        }

        ProcessBuilder builder = createProcessBuilder(directory);
        process = builder.start();
        System.out.println("quant-a started, pid=" + getPid(process) + ", health=" + healthUrl);

        if (!waitUntilHealthy(healthUrl)) {
            throw new IllegalStateException("quant-a health check failed after startup: " + healthUrl);
        }
    }

    @PreDestroy
    public void stopQuantA() {
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
        String normalizedPath = healthPath.startsWith("/") ? healthPath : "/" + healthPath;
        return "http://127.0.0.1:" + port + normalizedPath;
    }

    ProcessBuilder createProcessBuilder(File directory) {
        ProcessBuilder builder = new ProcessBuilder(
                command,
                "-m",
                "uvicorn",
                "main:app",
                "--host",
                "127.0.0.1",
                "--port",
                String.valueOf(port)
        );
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

    boolean isHealthy(String healthUrl) {
        HttpURLConnection connection = null;
        try {
            URL url = new URL(healthUrl);
            connection = (HttpURLConnection) url.openConnection();
            connection.setRequestMethod("GET");
            connection.setConnectTimeout(2000);
            connection.setReadTimeout(3000);
            int responseCode = connection.getResponseCode();
            if (responseCode < 200 || responseCode >= 300) {
                return false;
            }

            String body = readResponseBody(connection);
            return body.replaceAll("\\s+", "").contains("\"success\":true");
        } catch (IOException e) {
            return false;
        } finally {
            if (connection != null) {
                connection.disconnect();
            }
        }
    }

    private String readResponseBody(HttpURLConnection connection) throws IOException {
        StringBuilder builder = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(connection.getInputStream(), StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                builder.append(line);
            }
        }
        return builder.toString();
    }

    private String getPid(Process startedProcess) {
        try {
            return String.valueOf(startedProcess.getClass().getMethod("pid").invoke(startedProcess));
        } catch (Exception e) {
            return "unknown";
        }
    }
}
