package com.example.website.integration.scrapling;

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
 * Scrapling 抓取工坊（{@code website/scrapling-ui}，默认端口 5176）的按需启动器。
 *
 * <p>属于 website 的 integration 适配层，与 {@link ScraplingUiProperties}、
 * {@link ServiceHealthChecker} 协作，只负责定位目录、选择 Python 解释器、拉起
 * {@code uvicorn main:app} 并轮询 {@code /api/health}；页面抓取、代码生成与
 * Playwright 会话全部留在 Python 侧。</p>
 *
 * <p>关键行为：</p>
 * <ul>
 *   <li>幂等：{@link #start()} 先探测健康地址，已在线直接返回 {@code already-running}，
 *       复用使用者手动或用 uv 起的实例。</li>
 *   <li>解释器优先级：{@code command} 的基名为 {@code uv}（默认）时，依次尝试
 *       {@code backend/.venv/Scripts/python.exe}、{@code backend/.venv/bin/python}，
 *       都缺失才退回 {@code uv run python}；显式配置成其他命令（例如全局 Python 3.12
 *       的绝对路径）时直接执行该命令并绕过 {@code .venv}。</li>
 *   <li>前置校验：必须先有 {@code backend} 目录与已构建的 {@code frontend/dist/index.html}，
 *       否则不启动并给出构建指引。</li>
 *   <li>等待：最多 {@code startup-timeout-seconds}（默认 90）秒，每秒探测一次；
 *       超时后强杀本次拉起的子进程，避免留下半启动的 uvicorn。</li>
 *   <li>日志：默认 {@code inheritIO()} 进 website 控制台，关闭后追加写入
 *       {@code backend/server.out.log} 与 {@code backend/server.err.log}。</li>
 *   <li>生命周期：只由首页卡片点击启动，website 关闭时不强杀。</li>
 * </ul>
 */
@Component
@ConditionalOnProperty(prefix = "scrapling-ui.click-start", name = "enabled", havingValue = "true")
public class ScraplingUiProcessManager {

    private static final String SERVICE_NAME = "scrapling-ui";

    private final ServiceHealthChecker healthChecker;
    private final ScraplingUiProperties properties;

    private Process process;

    public ScraplingUiProcessManager(ServiceHealthChecker healthChecker, ScraplingUiProperties properties) {
        this.healthChecker = healthChecker;
        this.properties = properties;
    }

    /**
     * 启动或复用 Scrapling 抓取工坊。
     *
     * <p>方法带 {@code synchronized}：并发点击会排队，不会同时拉起两个 uvicorn。
     * 校验顺序为：已健康则复用 → 解析工作目录 → 校验 {@code backend} 目录 →
     * 校验 {@code frontend/dist/index.html} → 起进程 → 等待健康。</p>
     *
     * @return 已在线为 {@code already-running}，本次拉起并确认健康为 {@code started}
     * @throws ScraplingUiStartException 工作目录无法解析、缺少后端目录、前端尚未构建、
     *         Python 或 uv 无法执行，或在 {@code startup-timeout-seconds} 秒内
     *         未通过健康检查
     */
    public synchronized ScraplingUiStartResult start() {
        String healthUrl = buildHealthUrl();
        if (isHealthy(healthUrl)) {
            return new ScraplingUiStartResult(ScraplingUiStartResult.STATUS_ALREADY_RUNNING, appUrl());
        }

        File workDir;
        try {
            workDir = resolveWorkDir();
        } catch (IOException e) {
            throw new ScraplingUiStartException("scrapling-ui 工作目录解析失败：" + e.getMessage());
        }

        File backendDir = new File(workDir, "backend");
        if (!backendDir.isDirectory()) {
            throw new ScraplingUiStartException("scrapling-ui 后端目录不存在：" + backendDir.getAbsolutePath());
        }

        File distIndex = new File(workDir, "frontend" + File.separator + "dist" + File.separator + "index.html");
        if (!distIndex.isFile()) {
            throw new ScraplingUiStartException(
                    "scrapling-ui 前端尚未构建，请先在 website/scrapling-ui/frontend 执行 "
                            + "npm install && npm run build");
        }

        try {
            ProcessBuilder builder = createProcessBuilder(backendDir);
            process = builder.start();
        } catch (IOException e) {
            throw new ScraplingUiStartException(
                    "scrapling-ui 启动失败，请检查 click-start.command 指定的 Python 与依赖；使用 uv 时请执行 uv sync。原因："
                            + e.getMessage());
        }

        if (!waitUntilHealthy(healthUrl)) {
            stopStartedProcess();
            throw new ScraplingUiStartException(
                    "scrapling-ui 在 " + properties.getStartupTimeoutSeconds() + " 秒内未就绪，请检查后端日志");
        }

        return new ScraplingUiStartResult(ScraplingUiStartResult.STATUS_STARTED, appUrl());
    }

    /**
     * 实时探测是否已在线，只读不启动。
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
     * 拼接本机健康检查地址，形如 {@code http://127.0.0.1:5176/api/health}。
     *
     * @return 健康地址；端口与路径来自 {@link ScraplingUiProperties}
     */
    String buildHealthUrl() {
        return healthChecker.buildLocalUrl(properties.getPort(), properties.getHealthPath());
    }

    /**
     * 解析 {@code website/scrapling-ui} 模块目录，兼容从仓库根目录与 website 模块目录启动。
     *
     * <p>顺序：绝对路径直接采用；否则先试 {@code user.dir/<work-dir>}；当前目录本身是
     * {@code website} 模块目录且配置以 {@code website/} 开头时，去掉前缀再按模块目录拼接；
     * 以上都不存在时退回上一级目录。返回值不校验存在性，由后续 {@code backend} 目录校验
     * 给出明确提示。</p>
     *
     * @return 规范化后的绝对路径
     * @throws IOException 当前目录或目标路径无法规范化
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

        File fromParentDir = new File(parentDir, workDir);
        return fromParentDir.getCanonicalFile();
    }

    /**
     * 构造 {@code <python> -m uvicorn main:app --host 127.0.0.1 --port 5176} 启动器。
     *
     * <p>固定绑定 {@code 127.0.0.1}，不对外暴露抓取工作台；同时注入
     * {@code PYTHONUTF8=1}、{@code PYTHONIOENCODING=utf-8}、{@code PYTHONUNBUFFERED=1}。
     * Windows 控制台默认 GBK，日志中的特殊符号一旦编码失败会打断进程，固定 UTF-8 并
     * 关闭输出缓冲可同时规避乱码与截断。</p>
     *
     * @param backendDir 已解析的 {@code backend} 目录，作为子进程工作目录
     * @return 尚未启动的 {@link ProcessBuilder}，日志路由已按配置设置
     */
    ProcessBuilder createProcessBuilder(File backendDir) {
        List<String> commandParts = resolvePythonCommand(backendDir);
        commandParts.add("-m");
        commandParts.add("uvicorn");
        commandParts.add("main:app");
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

    /**
     * 选择 Python 解释器并拼出命令前缀。
     *
     * <p>默认命令 {@code uv}（可经 {@code SCRAPLING_UI_COMMAND} 覆盖）：先用
     * {@code backend/.venv} 里的解释器（Windows 为 {@code Scripts/python.exe}，其他平台为
     * {@code bin/python}），缺失时退回 {@code uv run python}，由 uv 管理环境。若配置的是
     * 其他可执行文件（例如全局 Python 3.12 的绝对路径），说明调用方已自行准备依赖，
     * 直接执行该命令以跳过 {@code .venv}，此时要求解释器版本不低于 3.12。</p>
     *
     * @param backendDir {@code backend} 目录，用于探测 {@code .venv}
     * @return 命令前缀，调用方继续追加 {@code -m uvicorn main:app ...}
     */
    private List<String> resolvePythonCommand(File backendDir) {
        List<String> commandParts = new ArrayList<String>();
        String configuredCommand = properties.getCommand();
        String executableName = new File(configuredCommand).getName();
        if (!"uv".equalsIgnoreCase(executableName) && !"uv.exe".equalsIgnoreCase(executableName)) {
            commandParts.add(configuredCommand);
            return commandParts;
        }

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

    /**
     * 处理「当前工作目录已经是 website 模块目录」的情况。
     *
     * <p>配置项默认写成相对仓库根目录的 {@code website/scrapling-ui}。在 IDE 中直接运行
     * website 模块时，当前目录已是 {@code .../website}，再拼一次会得到不存在的
     * {@code .../website/website/scrapling-ui}，因此先去掉 {@code website/} 前缀。</p>
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
     * stdout/stderr，便于在 IDE 控制台直接看到访问日志；为 {@code false} 时追加写入
     * {@code backend} 目录下的 {@code server.out.log} 与 {@code server.err.log}，
     * 追加而非覆盖，便于跨次启动回溯。</p>
     *
     * @param builder   待配置的启动器
     * @param directory 日志落地目录，通常是 {@code backend} 目录
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
     * {@code startup-timeout-seconds}（默认 90）次；单次探测仍受全局
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
     * 清理启动失败后残留的子进程。
     *
     * <p>先 {@code destroy()} 发正常终止请求，等待 5 秒仍未退出则 {@code destroyForcibly()}；
     * 只处理本类拉起的子进程，复用的外部实例不受影响。等待被中断时恢复中断标志并强制终止。</p>
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
