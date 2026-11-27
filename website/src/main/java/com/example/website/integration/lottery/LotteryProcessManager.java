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
 * 开奖数据操作台（{@code website/lottery}，独立 Python 服务，默认端口 5179）的按需启动器。
 *
 * <p>属于 {@code website} 的 integration 适配层，与 {@link LotteryProperties}、
 * {@link ServiceHealthChecker} 协作，只负责「解析目录 → 拼命令 → 起进程 → 轮询
 * {@code /api/health} → 报告结果」。开奖历史数据、组合分布与回测全部留在 Python 服务内，
 * 本类不做任何业务解释。</p>
 *
 * <p>关键行为：</p>
 * <ul>
 *   <li>幂等：{@link #start()} 先探测健康地址，已在线则直接返回 {@code already-running}，
 *       不重复起进程，也不接管已有的外部实例。</li>
 *   <li>命令：{@code <command> server.py --port <port>}，工作目录为解析后的
 *       {@code website/lottery}；默认命令 {@code python}，端口 5179。</li>
 *   <li>等待：最长为 {@code startup-timeout-seconds}（默认 60）秒，每秒探测一次；
 *       本类不检查子进程是否存活，因此端口被其他应用占用时要等满超时才失败，
 *       错误体只会说「未就绪」，不会指出端口冲突。</li>
 *   <li>失败清理：超时后只强杀本次拉起的子进程（先 {@code destroy()}，5 秒不退再
 *       {@code destroyForcibly()}），复用的外部实例不受影响。</li>
 *   <li>日志：默认 {@code inheritIO()} 输出到 website 控制台；关闭 {@code log-to-console}
 *       时追加写入工作目录下的 {@code server.out.log} 与 {@code server.err.log}。</li>
 *   <li>生命周期：只在首页卡片点击时启动，website 关闭时不强杀该服务。</li>
 * </ul>
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

    /**
     * 启动或复用开奖数据操作台。
     *
     * <p>方法带 {@code synchronized}：并发点击会排队串行执行，不会同时对同一端口
     * 拉起两个进程。先探测健康地址，已在线直接复用；否则校验 {@code server.py}
     * 后启动并等待就绪。</p>
     *
     * @return 已在线为 {@code already-running}，本次拉起并确认健康为 {@code started}
     * @throws LotteryStartException 工作目录无法解析、缺少 {@code server.py}、
     *         {@code python} 不可执行，或在 {@code startup-timeout-seconds} 秒内
     *         始终未通过健康检查
     */
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

    /**
     * 实时探测服务是否在线。
     *
     * <p>与 {@link #start()} 不同，这里只读探测、不启动任何进程，首页状态刷新可安全调用。</p>
     *
     * @return {@code true} 表示 {@code /api/health} 返回 2xx 且响应顶层 {@code success=true}
     */
    public boolean isRunning() {
        return isHealthy(buildHealthUrl());
    }

    public String appUrl() {
        return "http://127.0.0.1:" + properties.getPort() + "/";
    }

    /**
     * 拼接本机健康检查地址，形如 {@code http://127.0.0.1:5179/api/health}。
     *
     * @return 健康地址；端口与路径来自 {@link LotteryProperties}，路径缺少前导斜杠时会自动补齐
     */
    String buildHealthUrl() {
        return healthChecker.buildLocalUrl(properties.getPort(), properties.getHealthPath());
    }

    /**
     * 解析 Python 服务的工作目录，兼容「从仓库根目录启动」与「从 website 模块目录启动」。
     *
     * <p>顺序：绝对路径直接采用；否则先试 {@code user.dir/<work-dir>}；若当前目录本身
     * 就是 {@code website} 模块目录且配置以 {@code website/} 开头，去掉前缀后再拼，
     * 避免拼出不存在的 {@code website/website/lottery}；以上都不存在时退回上一级目录，
     * 由后续 {@code server.py} 存在性校验给出明确错误。</p>
     *
     * @return 规范化后的绝对路径；目录不存在时同样返回，交由调用方校验
     * @throws IOException 当前目录或目标路径无法规范化（例如权限不足）
     */
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

    /**
     * 构造 {@code python server.py --port 5179} 的启动器。
     *
     * <p>除命令与工作目录外还注入 {@code PYTHONUTF8=1}、{@code PYTHONIOENCODING=utf-8}、
     * {@code PYTHONUNBUFFERED=1} 和 {@code LOTTERY_PORT}。Windows 控制台默认 GBK，
     * 日志里的中文与特殊符号一旦编码失败会直接打断进程；固定 UTF-8 并关闭输出缓冲
     * 可同时规避截断与乱码。</p>
     *
     * @param workDir 已解析的工作目录，作为子进程的 {@code user.dir}
     * @return 尚未启动的 {@link ProcessBuilder}，日志路由已按配置设置
     */
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

    /**
     * 处理「当前工作目录已经是 website 模块目录」的情况。
     *
     * <p>配置项默认写成相对仓库根目录的 {@code website/lottery}。在 IDE 中直接运行
     * website 模块时，当前目录已是 {@code .../website}，再拼一次会得到不存在的
     * {@code .../website/website/lottery}，因此先去掉 {@code website/} 前缀。</p>
     *
     * @param currentDir 已规范化的当前工作目录
     * @param workDir    配置中的相对路径
     * @return 去掉前缀后的候选目录；当前目录名不是 {@code website}、或配置不以
     *         {@code website/} 开头时返回 {@code null}，由调用方继续回退
     */
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

    /**
     * 设置子进程日志路由。
     *
     * <p>{@code log-to-console} 为 {@code true} 时用 {@code inheritIO()} 复用 website 的
     * stdout/stderr，便于在 IDE 控制台直接看到服务访问日志；为 {@code false} 时追加写入
     * 工作目录下的 {@code server.out.log} 与 {@code server.err.log}，追加而非覆盖，
     * 便于跨次启动回溯。</p>
     *
     * @param builder   待配置的启动器
     * @param directory 日志落地目录，通常是已解析的工作目录
     */
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

    /**
     * 阻塞等待健康检查通过。
     *
     * <p>委托 {@link ServiceHealthChecker#waitUntilHealthy}：每秒探测一次，最多
     * {@code startup-timeout-seconds}（默认 60）次；单次探测仍受全局
     * {@code website.service-health} 的连接与读取超时约束，因此实际耗时可能略超配置值。</p>
     *
     * @param healthUrl 已拼好的健康地址
     * @return {@code true} 表示期间某次探测通过；超时返回 {@code false}
     */
    private boolean waitUntilHealthy(String healthUrl) {
        return healthChecker.waitUntilHealthy(
                new ServiceHealthDefinition(SERVICE_NAME, healthUrl), properties.getStartupTimeoutSeconds());
    }

    private boolean isHealthy(String healthUrl) {
        return healthChecker.check(new ServiceHealthDefinition(SERVICE_NAME, healthUrl)).isHealthy();
    }

    /**
     * 清理本次启动失败时残留的子进程。
     *
     * <p>先 {@code destroy()} 发正常终止请求，等待 5 秒仍未退出则 {@code destroyForcibly()}；
     * 只处理本类持有句柄的子进程，因此在复用外部已在线实例的场景下不会误杀他人进程。
     * 等待被中断时恢复中断标志并强制终止，避免吞掉中断状态。</p>
     */
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
