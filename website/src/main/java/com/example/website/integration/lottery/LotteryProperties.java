package com.example.website.integration.lottery;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * {@code lottery.click-start} 的配置绑定（开奖数据操作台点击启动参数）。
 *
 * <p>由 Spring Boot 从 {@code application.yml} 绑定，缺省值即 website 的默认行为：
 * 目录 {@code website/lottery}、命令 {@code python}、端口 {@code 5179}、
 * 健康路径 {@code /api/health}、启动等待 {@code 60} 秒、日志输出到控制台。
 * 字段保持可变，便于测试直接构造配置，无需启动 Spring 容器。</p>
 */
@Component
@ConfigurationProperties(prefix = "lottery.click-start")
public class LotteryProperties {

    /** 是否注册点击启动端点与进程管理器；为 {@code false} 时相关 Bean 不创建，端点返回 404。 */
    private boolean enabled = true;
    /** 服务目录，相对路径按 {@code user.dir} 及其父目录依次尝试；默认 {@code website/lottery}。 */
    private String workDir = "website/lottery";
    /** Python 可执行命令，默认 {@code python}；需要虚拟环境时可直接改为解释器绝对路径。 */
    private String command = "python";
    /** 服务监听端口，同时用于健康检查和入口地址；默认 5179。 */
    private int port = 5179;
    /** 健康检查路径，相对于 {@code http://127.0.0.1:<port>}；默认 {@code /api/health}。 */
    private String healthPath = "/api/health";
    /** 启动后等待健康通过的最长秒数；默认 60，期间每秒探测一次。 */
    private int startupTimeoutSeconds = 60;
    /** 是否把子进程 stdout/stderr 继承到 website 控制台；为 {@code false} 时写入服务目录下的日志文件。 */
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
