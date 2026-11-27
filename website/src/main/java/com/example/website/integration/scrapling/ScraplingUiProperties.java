package com.example.website.integration.scrapling;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * {@code scrapling-ui.click-start} 的配置绑定（Scrapling 抓取工坊点击启动参数）。
 *
 * <p>缺省值即默认行为：目录 {@code website/scrapling-ui}、命令 {@code uv}（可经
 * {@code SCRAPLING_UI_COMMAND} 覆盖）、端口 {@code 5176}、健康路径 {@code /api/health}、
 * 启动等待 {@code 90} 秒、日志输出到控制台。字段保持可变，便于测试直接构造配置，
 * 无需启动 Spring 容器。</p>
 */
@Component
@ConfigurationProperties(prefix = "scrapling-ui.click-start")
public class ScraplingUiProperties {

    /** 是否注册点击启动端点与进程管理器；为 {@code false} 时相关 Bean 不创建。 */
    private boolean enabled = true;
    /** 服务目录，指向同时包含 {@code backend} 与 {@code frontend} 的模块根目录；默认 {@code website/scrapling-ui}。 */
    private String workDir = "website/scrapling-ui";
    /** Python 启动命令；默认 {@code uv} 会优先使用 {@code backend/.venv}，其他取值则作为解释器直接执行。 */
    private String command = "uv";
    /** 服务监听端口，同时用于健康检查和入口地址；默认 5176。 */
    private int port = 5176;
    /** 健康检查路径，相对于 {@code http://127.0.0.1:<port>}；默认 {@code /api/health}。 */
    private String healthPath = "/api/health";
    /** 启动后等待健康通过的最长秒数；默认 90，首次导入 Scrapling 与 Playwright 依赖明显慢于热启动。 */
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
