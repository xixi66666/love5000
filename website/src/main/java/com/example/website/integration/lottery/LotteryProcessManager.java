package com.example.website.integration.lottery;

import com.example.website.integration.health.ServiceHealthChecker;
import com.example.website.integration.health.ServiceHealthDefinition;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;

/**
 * 按需启动/复用 website/lottery 开奖数据操作台（独立 Python 服务，默认端口 5179）。
 * 只在首页卡片点击时启动，website 关闭时不强杀。
 */
@Component
@ConditionalOnProperty(prefix = "lottery.click-start", name = "enabled", havingValue = "true")
public class LotteryProcessManager {

    private static final String SERVICE_NAME = "lottery";

    private final ServiceHealthChecker healthChecker;
    private final LotteryProperties properties;

    private Process process;

    public LotteryProcessManager(ServiceHealthChecker healthChecker, LotteryProperties properties) {
        this.healthChecker = healthChecker;
        this.properties = properties;
    }

    public synchronized LotteryStartResult start() {
        String healthUrl = buildHealthUrl();
        if (isHealthy(healthUrl)) {
            return new LotteryStartResult(LotteryStartResult.STATUS_ALREADY_RUNNING, appUrl());
        }

        File workDir;
        try {
            workDir = resolveWorkDir();
        } catch (IOException e) {
            throw new LotteryStartException("开奖数据操作台工作目录解析失败：" + e.getMessage());
        }

        File serverScript = new File(workDir, "server.py");
        if (!serverScript.isFile()) {
            throw new LotteryStartException("开奖数据操作台缺少 server.py：" + serverScript.getAbsolutePath());
        }

        try {
            process = createProcessBuilder(workDir).start();
        } catch (IOException e) {
            throw new LotteryStartException(
                    "开奖数据操作台启动失败，请确认 python 可用且已安装 numpy / pandas / requests。原因：" + e.getMessage());
        }

        if (!waitUntilHealthy(healthUrl)) {
            stopStartedProcess();
            throw new LotteryStartException(
                    "开奖数据操作台在 " + properties.getStartupTimeoutSeconds() + " 秒内未就绪，请检查服务日志");
        }

        return new LotteryStartResult(LotteryStartResult.STATUS_STARTED, appUrl());
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

        return new File(parentDir, workDir).getCanonicalFile();
    }

    ProcessBuilder createProcessBuilder(File workDir) {
        List<String> commandParts = new ArrayList<String>();
        commandParts.add(properties.getCommand());
        commandParts.add("server.py");
        commandParts.add("--port");
        commandParts.add(String.valueOf(properties.getPort()));

        ProcessBuilder builder = new ProcessBuilder(commandParts);
        builder.directory(workDir);
        builder.environment().put("PYTHONUTF8", "1");
        builder.environment().put("PYTHONIOENCODING", "utf-8");
        builder.environment().put("PYTHONUNBUFFERED", "1");
        builder.environment().put("LOTTERY_PORT", String.valueOf(properties.getPort()));
        configureLogging(builder, workDir);
        return builder;
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
