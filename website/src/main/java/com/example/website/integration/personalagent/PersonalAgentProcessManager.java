package com.example.website.integration.personalagent;

import com.example.website.integration.health.ServiceHealthProperties;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.URL;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;

/**
 * 个人长期资料库（仓库根目录 {@code personal-agent}，端口 5178）的按需启动器。
 *
 * <p>属于 website 的 integration 适配层：定位 Maven 产物、拉起 {@code java -jar}、
 * 轮询健康接口并报告结果；Vault、Quartz 与 AI 分析等业务逻辑全部留在
 * personal-agent 模块内，这里不做任何越界处理。</p>
 *
 * <p>关键行为：</p>
 * <ul>
 *   <li>幂等：已健康直接返回 {@code already-running}；本类自己拉起且仍存活的进程会被
 *       等待复用，不会重复启动第二个实例。</li>
 *   <li>端口归属：启动前用 {@link #probeHealth()} 区分「自己还没就绪」与「端口被别的
 *       应用占用」，后者直接报错，不启动、不覆盖、也不去停止占用者。</li>
 *   <li>命令：{@code <java> -jar target/personal-agent-0.0.1-SNAPSHOT.jar
 *       --server.address=127.0.0.1 --server.port=<port>}，工作目录为 {@code personal-agent}；
 *       未配置命令时取当前 JVM 的 {@code java.home/bin/java}。</li>
 *   <li>等待：最多 {@code startup-timeout-seconds}（默认 90）秒，每 250 毫秒探测一次；
 *       超时后不杀进程，因为慢启动的 JVM 往往只差几秒，下次点击会复用这个进程。</li>
 *   <li>日志：默认 {@code inheritIO()} 进 website 控制台；关闭后追加写入工作目录下的
 *       {@code server.out.log} 与 {@code server.err.log}。</li>
 *   <li>生命周期：只由 03 Deep Woods 卡片点击启动，website 关闭时不强杀。</li>
 * </ul>
 */
@Component
@ConditionalOnProperty(prefix = "personal-agent.click-start", name = "enabled", havingValue = "true")
public class PersonalAgentProcessManager {

    /**
     * 健康探测结论。
     *
     * <p>之所以不用 {@link com.example.website.integration.health.ServiceHealthChecker}
     * 的布尔结果，是因为启动前必须区分「端口空闲」与「端口被其他应用占用」。后者若被
     * 当成普通的「未就绪」，就会往一个已被占用的端口拉进程，最终只得到一句含糊的超时错误。</p>
     *
     * <p>取值含义：{@code HEALTHY} 为端口在监听且 {@code /api/health} 返回 2xx、
     * {@code service=personal-agent}、{@code success=true}；{@code UNAVAILABLE} 为端口没有
     * 进程监听，可以安全启动；{@code NOT_READY} 为本服务的端口但健康检查尚未通过；
     * {@code OCCUPIED} 为端口在监听但响应不来自本服务或读取失败，此时拒绝启动。</p>
     */
    enum HealthStatus { HEALTHY, UNAVAILABLE, NOT_READY, OCCUPIED }

    /** 解析健康响应体，用于识别其中的 {@code service} 字段。 */
    private final ObjectMapper objectMapper;
    /** 全局健康检查超时配置；这里复用其连接与读取超时，避免本机探测长期占住请求线程。 */
    private final ServiceHealthProperties healthProperties;
    /** 点击启动配置：工作目录、Java 命令、端口、等待秒数与日志路由。 */
    private final PersonalAgentProperties properties;
    /** 最近一次由本类拉起的子进程；为 {@code null} 或已退出时不影响对已在线外部实例的复用。 */
    private Process process;

    public PersonalAgentProcessManager(ObjectMapper objectMapper, ServiceHealthProperties healthProperties,
                                       PersonalAgentProperties properties) {
        this.objectMapper = objectMapper;
        this.healthProperties = healthProperties;
        this.properties = properties;
    }

    /**
     * 启动或复用个人资料库。
     *
     * <p>方法带 {@code synchronized}：并发点击会排队，避免同时对同一端口起进程。
     * 判定顺序为：已健康则复用；端口被他人占用则直接失败；本类拉起的进程仍在则等它就绪；
     * 处于未就绪状态或端口已在用则失败；否则校验 jar 后启动。</p>
     *
     * @return 已在线为 {@code already-running}，本次拉起并确认健康为 {@code started}
     * @throws PersonalAgentStartException 端口已被占用或已有实例未就绪、工作目录无法解析、
     *         尚未构建 jar、Java 无法执行，或在 {@code startup-timeout-seconds} 秒内
     *         未通过健康检查
     */
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
            throw new PersonalAgentStartException("个人资料库 工作目录解析失败，请检查 personal-agent.click-start.work-dir");
        }
        if (!jarFile(workDir).isFile()) {
            throw new PersonalAgentStartException("个人资料库 尚未构建，请先在仓库根目录执行 "
                    + "mvn -pl personal-agent -am package -DskipTests");
        }

        try {
            process = launch(createProcessBuilder(workDir));
        } catch (IOException exception) {
            throw new PersonalAgentStartException("个人资料库 启动失败，请检查 Java 运行环境或 "
                    + "PERSONAL_AGENT_COMMAND 指定的 Java 可执行文件，以及 Maven 构建产物");
        }
        if (!waitUntilHealthy()) {
            throw notReady();
        }
        return result(PersonalAgentStartResult.STATUS_STARTED);
    }

    /**
     * 实时探测是否已在线，只读不启动。
     *
     * @return {@code true} 表示端口在监听且响应中 {@code service=personal-agent}、
     *         {@code success=true}
     */
    public boolean isRunning() {
        return probeHealth() == HealthStatus.HEALTHY;
    }

    public String appUrl() {
        return "http://127.0.0.1:" + properties.getPort() + "/";
    }

    /**
     * 拼接本机健康检查地址，形如 {@code http://127.0.0.1:5178/api/health}。
     *
     * @return 健康地址；{@code health-path} 缺少前导斜杠时会补齐
     */
    String buildHealthUrl() {
        String path = properties.getHealthPath();
        return appUrl() + (path.startsWith("/") ? path.substring(1) : path);
    }

    /**
     * 解析 personal-agent 模块目录。
     *
     * <p>顺序：绝对路径直接采用；否则先试 {@code user.dir/<work-dir>}；不存在时退回上一级
     * 目录，覆盖「从仓库根目录启动」与「从 website 模块目录启动」两种方式。该模块位于
     * 仓库根目录而不是 {@code website/} 下，因此无需处理 {@code website/} 前缀。</p>
     *
     * @return 规范化后的绝对路径；目录不存在时也会返回，由 jar 存在性校验给出明确错误
     * @throws IOException 当前目录或目标路径无法规范化
     */
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

    /**
     * 构造 {@code java -jar ... --server.address=127.0.0.1 --server.port=<port>} 启动器。
     *
     * <p>显式传入 {@code --server.address} 与 {@code --server.port}：前者让服务只监听回环
     * 地址，后者让端口以 website 的配置为准，避免 personal-agent 自身默认配置与之不一致。</p>
     *
     * @param workDir personal-agent 模块目录，同时作为子进程工作目录和日志落地目录
     * @return 尚未启动的 {@link ProcessBuilder}，日志路由已按配置设置
     */
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

    /**
     * 解析 Java 可执行文件。
     *
     * <p>优先使用配置的 {@code command}（可经 {@code PERSONAL_AGENT_COMMAND} 覆盖），
     * 便于指定特定 JDK；未配置时取当前运行 website 的 JVM 同目录下的 {@code bin/java}
     * （Windows 为 {@code java.exe}），保证子进程与父进程版本一致。</p>
     *
     * @return 可直接执行的命令字符串
     */
    private String resolveJavaCommand() {
        String configured = properties.getCommand();
        if (configured != null && !configured.trim().isEmpty()) {
            return configured;
        }
        File executable = new File(System.getProperty("java.home"),
                "bin" + File.separator + (File.separatorChar == '\\' ? "java.exe" : "java"));
        return executable.getAbsolutePath();
    }

    /**
     * 定位 Maven 构建产物，固定为 {@code target/personal-agent-0.0.1-SNAPSHOT.jar}。
     *
     * @param workDir personal-agent 模块目录
     * @return jar 文件句柄；可能并不存在，由调用方校验
     */
    private File jarFile(File workDir) {
        return new File(workDir, "target" + File.separator + "personal-agent-0.0.1-SNAPSHOT.jar");
    }

    /**
     * 启动子进程。
     *
     * <p>单独抽成包级方法是为测试留出替换点，避免单测真的拉起 JVM。</p>
     *
     * @param builder 已配置好的启动器
     * @return 已启动的进程
     * @throws IOException 命令不存在、工作目录不可用或操作系统拒绝创建进程
     */
    Process launch(ProcessBuilder builder) throws IOException {
        return builder.start();
    }

    /**
     * 打开健康检查连接。
     *
     * <p>包级可见以便测试替换成内存连接，避免单测访问真实端口。</p>
     *
     * @return 尚未设置请求方法的 {@link HttpURLConnection}
     * @throws IOException 地址非法或无法创建连接
     */
    HttpURLConnection openHealthConnection() throws IOException {
        return (HttpURLConnection) new URL(buildHealthUrl()).openConnection();
    }

    /**
     * 探测端口与健康接口，得出四态结论。
     *
     * <p>先做 {@link #isPortInUse()} 端口探测，未监听直接判为未运行；端口在监听时再请求
     * {@code /api/health}，只有「2xx + {@code service=personal-agent} + {@code success=true}」
     * 才算健康。响应体缺 {@code service} 字段、响应体读不出来或连接异常时判为端口被其他
     * 应用占用；能读到 {@code service=personal-agent} 但状态码非 2xx 或 {@code success}
     * 不为真时判为未就绪。两种情况都会拒绝启动，区别只在错误提示的措辞。</p>
     *
     * @return 健康状态；探测本身不抛异常，失败都折算成状态值
     */
    HealthStatus probeHealth() {
        if (!isPortInUse()) {
            return HealthStatus.UNAVAILABLE;
        }
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
        } catch (IOException exception) {
            return HealthStatus.OCCUPIED;
        } finally {
            if (connection != null) {
                connection.disconnect();
            }
        }
    }

    /**
     * 判断端口是否有进程接受连接。
     *
     * <p>只做 TCP 连接，不看应用层响应；连接超时沿用全局
     * {@code website.service-health.connect-timeout-ms}（默认 2000 毫秒）。</p>
     *
     * @return {@code true} 表示三次握手成功，端口已被占用
     */
    boolean isPortInUse() {
        try (Socket socket = new Socket()) {
            socket.connect(new InetSocketAddress("127.0.0.1", properties.getPort()),
                    healthProperties.getConnectTimeoutMs());
            return true;
        } catch (IOException exception) {
            // 连接被拒绝或超时都表示没有进程接受连接，不能据此判定端口已被其他应用占用；
            // 本机防火墙丢弃 SYN 时会表现为超时，若误判为占用会导致服务永远无法启动。
            return false;
        }
    }

    /**
     * 轮询直到健康、子进程退出或超时。
     *
     * <p>每 250 毫秒探测一次，总时长上限为 {@code startup-timeout-seconds}（默认 90 秒，
     * 至少 1 秒）。等待期间若端口被其他应用抢走（探测结果变为占用）立即失败；若本类拉起
     * 的子进程退出也立即返回失败，不必等满超时。线程被中断时恢复中断标志并返回失败。</p>
     *
     * @return {@code true} 表示在超时前通过健康检查
     * @throws PersonalAgentStartException 等待期间发现 {@code 5178} 端口被其他应用占用
     */
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

    /**
     * 构造「端口被占用或已有实例尚未就绪」的错误。
     *
     * <p>文案里明确要求不要去停止其他应用，避免使用者误杀占用端口的无关进程。</p>
     *
     * @return 带端口号的可读异常
     */
    private PersonalAgentStartException occupiedPort() {
        return new PersonalAgentStartException("个人资料库 端口 " + properties.getPort()
                + " 已被占用或已有实例尚未就绪，请检查该端口；未启动或停止其他应用");
    }

    /**
     * 构造「等待超时」的错误。
     *
     * <p>文案说明再次点击会复用仍在启动的进程，与「超时不杀进程」的行为一致。</p>
     *
     * @return 带等待秒数的可读异常
     */
    private PersonalAgentStartException notReady() {
        return new PersonalAgentStartException("个人资料库 在 " + properties.getStartupTimeoutSeconds()
                + " 秒内未就绪，请检查服务日志；再次点击会复用仍在启动的进程");
    }
}
