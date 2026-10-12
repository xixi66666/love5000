package com.example.website.integration.skillfinder;

import com.example.website.integration.health.ServiceHealthChecker;
import com.example.website.integration.health.ServiceHealthDefinition;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;

@Component
@ConditionalOnProperty(prefix = "skill-finder.click-start", name = "enabled", havingValue = "true")
public class SkillFinderProcessManager {

    private static final String SERVICE_NAME = "skill-finder";

    private final ServiceHealthChecker healthChecker;
    private final SkillFinderProperties properties;

    private Process process;

    public SkillFinderProcessManager(ServiceHealthChecker healthChecker, SkillFinderProperties properties) {
        this.healthChecker = healthChecker;
        this.properties = properties;
    }

    public synchronized SkillFinderStartResult start() {
        String healthUrl = buildHealthUrl();
        if (isHealthy(healthUrl)) {
            return new SkillFinderStartResult(SkillFinderStartResult.STATUS_ALREADY_RUNNING, appUrl());
        }

        File workDir;
        try {
            workDir = resolveWorkDir();
        } catch (IOException e) {
            throw new SkillFinderStartException("skill-finder 工作目录解析失败：" + e.getMessage());
        }

        File backendDir = new File(workDir, "backend");
        if (!backendDir.isDirectory()) {
            throw new SkillFinderStartException("skill-finder 后端目录不存在：" + backendDir.getAbsolutePath());
        }

        File distIndex = new File(workDir, "frontend" + File.separator + "dist" + File.separator + "index.html");
        if (!distIndex.isFile()) {
            throw new SkillFinderStartException(
                    "skill-finder 前端尚未构建，请先在 website/skill-finder/frontend 执行 "
                            + "npm install && npm run build");
        }

        try {
            ProcessBuilder builder = createProcessBuilder(backendDir);
            process = builder.start();
        } catch (IOException e) {
            throw new SkillFinderStartException(
                    "skill-finder 启动失败，请确认已安装 uv 并在 website/skill-finder/backend 执行 uv sync。原因："
                            + e.getMessage());
        }

        if (!waitUntilHealthy(healthUrl)) {
            stopStartedProcess();
            throw new SkillFinderStartException(
                    "skill-finder 在 " + properties.getStartupTimeoutSeconds() + " 秒内未就绪，请检查后端日志");
        }

        return new SkillFinderStartResult(SkillFinderStartResult.STATUS_STARTED, appUrl());
    }

    public boolean isRunning() {
        return isHealthy(buildHealthUrl());
    }

    public String appUrl() {
        return "http://127.0.0.1:" + properties.getPort() + "/";
    }

    String buildHealthUrl() {
        return healthChecker.buildLocalUrl(properties.getPort(), properties.getHealthPath());
    }

    File resolveWorkDir() throws IOException {
        String workDir = properties.getWorkDir();
        File configured = new File(workDir);
        if (configured.isAbsolute()) {
            return configured.getCanonicalFile();
        }

        File currentDir = new File(System.getProperty("user.dir")).getCanonicalFile();
        File fromCurrentDir = new File(currentDir, workDir);
        if (fromCurrentDir.exists()) {
            return fromCurrentDir.getCanonicalFile();
        }

        File fromWebsiteModuleDir = resolveFromWebsiteModuleDir(currentDir, workDir);
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

    ProcessBuilder createProcessBuilder(File backendDir) {
        List<String> commandParts = resolvePythonCommand(backendDir);
        commandParts.add("-m");
        commandParts.add("uvicorn");
        commandParts.add("app.main:app");
        commandParts.add("--host");
        commandParts.add("127.0.0.1");
        commandParts.add("--port");
        commandParts.add(String.valueOf(properties.getPort()));

        ProcessBuilder builder = new ProcessBuilder(commandParts);
        builder.directory(backendDir);
        builder.environment().put("PYTHONUTF8", "1");
        builder.environment().put("PYTHONIOENCODING", "utf-8");
        builder.environment().put("PYTHONUNBUFFERED", "1");
        configureLogging(builder, backendDir);
        return builder;
    }

    private List<String> resolvePythonCommand(File backendDir) {
        List<String> commandParts = new ArrayList<String>();

        File windowsVirtualEnvPython = new File(backendDir,
                ".venv" + File.separator + "Scripts" + File.separator + "python.exe");
        if (windowsVirtualEnvPython.isFile()) {
            commandParts.add(windowsVirtualEnvPython.getAbsolutePath());
            return commandParts;
        }

        File unixVirtualEnvPython = new File(backendDir,
                ".venv" + File.separator + "bin" + File.separator + "python");
        if (unixVirtualEnvPython.isFile()) {
            commandParts.add(unixVirtualEnvPython.getAbsolutePath());
            return commandParts;
        }

        commandParts.add(properties.getCommand());
        commandParts.add("run");
        commandParts.add("python");
        return commandParts;
    }

    private File resolveFromWebsiteModuleDir(File currentDir, String workDir) {
        if (!"website".equals(currentDir.getName())) {
            return null;
        }

        String normalizedWorkDir = workDir.replace('\\', '/');
        if (!normalizedWorkDir.startsWith("website/")) {
            return null;
        }

        return new File(currentDir, normalizedWorkDir.substring("website/".length()));
    }

    private void configureLogging(ProcessBuilder builder, File directory) {
        if (properties.isLogToConsole()) {
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
                new ServiceHealthDefinition(SERVICE_NAME, healthUrl), properties.getStartupTimeoutSeconds());
    }

    private boolean isHealthy(String healthUrl) {
        return healthChecker.check(new ServiceHealthDefinition(SERVICE_NAME, healthUrl)).isHealthy();
    }

    private void stopStartedProcess() {
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
}
