package com.example.website.integration.skillfinder;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * {@code skill-finder.click-start} 的配置绑定（Skill Finder 点击启动参数）。
 *
 * <p>缺省值即默认行为：目录 {@code website/skill-finder}、命令 {@code uv}、端口
 * {@code 5177}、健康路径 {@code /api/health}、启动等待 {@code 90} 秒、
 * 日志输出到控制台。字段保持可变，便于测试直接构造配置，无需启动 Spring 容器。</p>
 */
@Component
@ConfigurationProperties(prefix = "skill-finder.click-start")
public class SkillFinderProperties {

    /** 是否注册点击启动端点与进程管理器；为 {@code false} 时相关 Bean 不创建。 */
    private boolean enabled = true;
    /** 服务目录，指向同时包含 {@code backend} 与 {@code frontend} 的模块根目录；默认 {@code website/skill-finder}。 */
    private String workDir = "website/skill-finder";
    /** 回退用的 Python 命令，仅在 {@code backend/.venv} 缺失时执行 {@code <command> run python}；默认 {@code uv}。 */
    private String command = "uv";
    /** 服务监听端口，同时用于健康检查和入口地址；默认 5177。 */
    private int port = 5177;
    /** 健康检查路径，相对于 {@code http://127.0.0.1:<port>}；默认 {@code /api/health}。 */
    private String healthPath = "/api/health";
    /** 启动后等待健康通过的最长秒数；默认 90，首次启动需连接 MySQL 并可能补建缺失业务表，明显慢于热启动。 */
    private int startupTimeoutSeconds = 90;
    /** 是否把子进程输出继承到 website 控制台；为 {@code false} 时写入 {@code backend} 下的日志文件。 */
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
