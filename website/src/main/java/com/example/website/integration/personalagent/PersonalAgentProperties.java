package com.example.website.integration.personalagent;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * {@code personal-agent.click-start} 的配置绑定（03 Deep Woods 个人资料库点击启动参数）。
 *
 * <p>缺省值即默认行为：目录 {@code personal-agent}（位于仓库根目录，不在 {@code website/}
 * 下）、命令为空（回退到当前 JVM 的 {@code java.home/bin/java}）、端口 {@code 5178}、
 * 健康路径 {@code /api/health}、启动等待 {@code 90} 秒、日志输出到控制台。
 * 字段保持可变，便于测试直接构造配置，无需启动 Spring 容器。</p>
 */
@Component
@ConfigurationProperties(prefix = "personal-agent.click-start")
public class PersonalAgentProperties {

    /** 是否注册点击启动端点与进程管理器；为 {@code false} 时相关 Bean 不创建。 */
    private boolean enabled = true;
    /** personal-agent 模块目录，相对路径按 {@code user.dir} 及其父目录依次尝试；默认 {@code personal-agent}。 */
    private String workDir = "personal-agent";
    /** Java 可执行命令；留空表示使用当前 website 进程所用的 JDK。 */
    private String command = "";
    /** 服务监听端口，同时用于健康检查和入口地址；默认 5178。 */
    private int port = 5178;
    /** 健康检查路径，相对于 {@code http://127.0.0.1:<port>}；默认 {@code /api/health}。 */
    private String healthPath = "/api/health";
    /** 启动后等待健康通过的最长秒数；默认 90，JVM 冷启动明显慢于 Python 服务。 */
    private int startupTimeoutSeconds = 90;
    /** 是否把子进程输出继承到 website 控制台；为 {@code false} 时写入模块目录下的日志文件。 */
    private boolean logToConsole = true;

    public boolean isEnabled() {
        return enabled;
    }

    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
    }

    public String getWorkDir() {
        return workDir;
    }

    public void setWorkDir(String workDir) {
        this.workDir = workDir;
    }

    public String getCommand() {
        return command;
    }

    public void setCommand(String command) {
        this.command = command;
    }

    public int getPort() {
        return port;
    }

    public void setPort(int port) {
        this.port = port;
    }

    public String getHealthPath() {
        return healthPath;
    }

    public void setHealthPath(String healthPath) {
        this.healthPath = healthPath;
    }

    public int getStartupTimeoutSeconds() {
        return startupTimeoutSeconds;
    }

    public void setStartupTimeoutSeconds(int startupTimeoutSeconds) {
        this.startupTimeoutSeconds = startupTimeoutSeconds;
    }

    public boolean isLogToConsole() {
        return logToConsole;
    }

    public void setLogToConsole(boolean logToConsole) {
        this.logToConsole = logToConsole;
    }
}
