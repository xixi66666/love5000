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

/**
 * python-a（A 股自选股 AI 研究台）自动启动器。
 *
 * <p>属于 website 的 integration 接入层：在 Spring Boot 启动收尾阶段保证
 * {@code http://127.0.0.1:5174} 上的 Python 服务可用，自身不承载任何股票业务逻辑，
 * 只负责「探测、复用或拉起、就绪确认、关闭时回收」。</p>
 *
 * <p>关键行为：</p>
 * <ul>
 *   <li>拉起前先请求 {@code /api/health}；已有健康实例时只打印复用日志并直接返回，
 *       避免与手工启动的实例争抢端口、重复拉起进程。</li>
 *   <li>仅当 {@code python-a.auto-start.enabled=true} 时装配。单元测试必须关闭该开关，
 *       否则测试会真的启动外部 Python 进程。</li>
 *   <li>解释器由 {@link PythonCommandResolver} 决定：优先工作目录下的 {@code .venv}，
 *       否则回退配置的 {@code python} 命令。</li>
 *   <li>工作目录兼容从仓库根目录、{@code website/} 模块目录和任意子目录启动，
 *       见 {@link #resolveWorkDir()}。</li>
 *   <li>拉起后最多等待 {@code startup-timeout-seconds}（默认 20 秒）确认就绪；
 *       超时或命令启动失败只向 stderr 输出告警，不中断 website 启动。</li>
 * </ul>
 *
 * <p>子进程日志默认继承父进程控制台（{@code log-to-console=true}）；关闭后分别追加到
 * 工作目录的 {@code server.out.log} 与 {@code server.err.log}。容器关闭时
 * {@link #stopPythonA()} 只结束本实例拉起的进程，复用到的既有实例保持运行。</p>
 *
 * @see PythonCommandResolver
 * @see ServiceHealthChecker
 */
@Component
@ConditionalOnProperty(prefix = "python-a.auto-start", name = "enabled", havingValue = "true")
public class PythonAAutoStartRunner implements ApplicationRunner {

    private static final String SERVICE_NAME = "python-a";

    private final ServiceHealthChecker healthChecker;

    @Value("${python-a.auto-start.work-dir:website/python-a}")
    private String workDir;

    @Value("${python-a.auto-start.command:python}")
    private String command;

    @Value("${python-a.auto-start.port:5174}")
    private int port;

    @Value("${python-a.auto-start.health-path:/api/health}")
    private String healthPath;

    @Value("${python-a.auto-start.startup-timeout-seconds:20}")
    private int startupTimeoutSeconds;

    @Value("${python-a.auto-start.log-to-console:true}")
    private boolean logToConsole;

    private Process process;

    /**
     * 无参构造，供测试和手动构造使用。
     *
     * <p>装配一个使用默认配置的健康检查器（2000/3000 毫秒超时），
     * 不注入 Spring 的 {@code @Value} 配置，因此需要显式赋值各配置字段。</p>
     */
    PythonAAutoStartRunner() {
        this(new ServiceHealthChecker(new ObjectMapper(), new ServiceHealthProperties()));
    }

    /**
     * 注入共享的单目标健康检查器。
     *
     * @param healthChecker 复用其 HTTP 超时配置和本地健康地址拼装能力
     */
    @Autowired
    public PythonAAutoStartRunner(ServiceHealthChecker healthChecker) {
        this.healthChecker = healthChecker;
    }

    /**
     * 启动阶段入口：复用健康实例，否则拉起 {@code server.py} 并等待就绪。
     *
     * <p>只有工作目录解析失败和目录不存在会中断启动；进程启动失败、就绪超时都只告警，
     * 因为自动启动是便利功能，不应让 website 整体起不来。</p>
     *
     * @param args Spring 启动参数，本方法不使用
     * @throws Exception 工作目录规范化为绝对路径失败时抛出
     * @throws IllegalStateException 配置的工作目录不存在或不是目录时抛出
     */
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

        try {
            ProcessBuilder builder = createProcessBuilder(directory);

            process = builder.start();
            System.out.println("python-a started, pid=" + getPid(process) + ", health=" + healthUrl);

            if (!waitUntilHealthy(healthUrl)) {
                warnAutoStartSkipped("health check failed after startup: " + healthUrl, null);
            }
        } catch (IOException e) {
            warnAutoStartSkipped("failed to start command '" + command + "' in " + directory.getAbsolutePath(), e);
        }
    }

    /**
     * 容器关闭时结束本实例拉起的 Python 进程。
     *
     * <p>先请求正常终止并最多等待 5 秒；超时或线程被中断时强制结束，同时恢复中断标记。
     * 复用到的既有实例不归本类管理，这里不会碰它。</p>
     */
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

    /**
     * 解析 python-a 的工作目录，兼容多种启动位置。
     *
     * <p>顺序为：绝对路径直接使用；相对路径先按当前工作目录（从仓库根目录启动）；
     * 再按 {@code website/} 模块目录（从模块内启动）；最后按当前目录的父目录。
     * 返回值统一规范化为绝对路径，用于设置子进程工作目录和日志文件位置。</p>
     *
     * @return 规范化的目录，不保证真实存在，由调用方校验
     * @throws IOException 路径规范化失败时抛出
     */
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

    /**
     * 从 {@code website/} 模块目录推导工作目录。
     *
     * <p>仅当当前目录名恰为 {@code website} 且配置路径以 {@code website/} 开头时生效，
     * 例如配置 {@code website/python-a} 会映射为 {@code <当前目录>/python-a}。</p>
     *
     * @param currentDir 当前工作目录
     * @return 推导出的目录；不适用时返回 {@code null}
     */
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

    /**
     * 构造 python-a 子进程的启动参数。
     *
     * <p>命令为「解释器加 server.py」，工作目录设为解析结果；注入 {@code PORT}
     * 让服务监听约定端口，注入 {@code PYTHONUNBUFFERED=1} 保证日志实时输出，
     * 避免默认缓冲导致控制台长时间看不到请求日志。</p>
     *
     * @param directory 已存在的工作目录
     * @return 尚未启动的 {@link ProcessBuilder}，输出重定向已配置
     */
    ProcessBuilder createProcessBuilder(File directory) {
        List<String> commandParts = PythonCommandResolver.resolve(command, directory);
        commandParts.add("server.py");

        ProcessBuilder builder = new ProcessBuilder(commandParts);
        builder.directory(directory);
        builder.environment().put("PORT", String.valueOf(port));
        builder.environment().put("PYTHONUNBUFFERED", "1");
        configureLogging(builder, directory);
        return builder;
    }

    /**
     * 配置子进程输出去处。
     *
     * <p>{@code log-to-console=true} 时用 inheritIO 把 stdout/stderr 直接接到 website 控制台；
     * 否则追加写入工作目录的 {@code server.out.log} 与 {@code server.err.log}，
     * 便于无控制台环境中排查启动失败。</p>
     *
     * @param builder   待配置的进程构造器
     * @param directory 日志文件所在目录
     */
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

    /**
     * 按启动超时轮询等待 python-a 就绪。
     *
     * @param healthUrl 健康检查地址
     * @return 在超时前就绪返回 {@code true}；超时或被中断返回 {@code false}
     */
    private boolean waitUntilHealthy(String healthUrl) {
        return healthChecker.waitUntilHealthy(
                new ServiceHealthDefinition(SERVICE_NAME, healthUrl), startupTimeoutSeconds);
    }

    /**
     * 探测一次健康接口，用于「已在线则复用」的判定，不重试。
     *
     * @param healthUrl 健康检查地址
     * @return HTTP 2xx 且响应顶层布尔值 {@code success=true} 时为 {@code true}
     */
    private boolean isHealthy(String healthUrl) {
        return healthChecker.check(new ServiceHealthDefinition(SERVICE_NAME, healthUrl)).isHealthy();
    }

    /**
     * 尽力取出子进程 PID 用于启动日志。
     *
     * <p>Java 8 的 {@link Process} 没有 {@code pid()} 方法，这里反射调用 Java 9 起提供的方法；
     * 取不到时返回 {@code unknown}，不影响启动流程。</p>
     *
     * @param startedProcess 已启动的进程
     * @return PID 文本，或 {@code unknown}
     */
    private String getPid(Process startedProcess) {
        try {
            return String.valueOf(startedProcess.getClass().getMethod("pid").invoke(startedProcess));
        } catch (Exception e) {
            return "unknown";
        }
    }

    /**
     * 输出自动启动失败告警，并附带手工启动与配置提示。
     *
     * <p>自动启动属于尽力而为的便利功能，失败不能阻断 website 启动，因此这里只写 stderr，
     * 不抛异常。</p>
     *
     * @param reason 失败原因，拼进告警文本
     * @param cause  底层异常，可为 {@code null}
     */
    private void warnAutoStartSkipped(String reason, Exception cause) {
        String message = "python-a auto-start skipped: " + reason
                + ". Start it manually or configure python-a.auto-start.command / website/python-a/.venv.";
        if (cause == null) {
            System.err.println(message);
            return;
        }
        System.err.println(message + " Cause: " + cause.getMessage());
    }
}
