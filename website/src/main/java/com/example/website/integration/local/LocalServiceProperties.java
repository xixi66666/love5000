package com.example.website.integration.local;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * 本机模型与视频服务的配置项，前缀 {@code website.local-services}。
 *
 * <p>三个服务都是宿主机上既有的独立应用，不随 website 启停，这里只保存它们的位置、
 * 端口与启动等待时长。默认值对应开发机：Strata 在 {@code F:/model/Strata}（9999）、
 * AIMedia 操作台在 {@code D:/Code/Java_Code/AIMedia}（8190）、H3 引擎为 AIMedia 下的
 * {@code ComfyUI}（8189）。application.yml 用 {@code STRATA_HOME}、
 * {@code AIMEDIA_HOME} 覆盖目录，便于换机器部署。</p>
 */
@Component
@ConfigurationProperties(prefix = "website.local-services")
public class LocalServiceProperties {
    /** Strata 项目根目录，其下需要有 {@code .venv} 与 {@code serve/server.py}。 */
    private String strataDir = "F:/model/Strata";
    /** AIMedia 项目根目录，H3 引擎位于其 {@code ComfyUI} 子目录。 */
    private String aimediaDir = "D:/Code/Java_Code/AIMedia";
    /** Strata 服务端口，默认 9999。 */
    private int strataPort = 9999;
    /** AIMedia 操作台端口，默认 8190。 */
    private int studioPort = 8190;
    /** H3（ComfyUI）引擎端口，默认 8189。 */
    private int h3Port = 8189;
    /** 启动后等待服务可用的最长时间，单位秒；默认 180，同时用作加载、卸载模型的读取超时。 */
    private int startupTimeoutSeconds = 180;

    public String getStrataDir() { return strataDir; }
    public void setStrataDir(String value) { strataDir = value; }
    public String getAimediaDir() { return aimediaDir; }
    public void setAimediaDir(String value) { aimediaDir = value; }
    public int getStrataPort() { return strataPort; }
    public void setStrataPort(int value) { strataPort = value; }
    public int getStudioPort() { return studioPort; }
    public void setStudioPort(int value) { studioPort = value; }
    public int getH3Port() { return h3Port; }
    public void setH3Port(int value) { h3Port = value; }
    public int getStartupTimeoutSeconds() { return startupTimeoutSeconds; }
    public void setStartupTimeoutSeconds(int value) { startupTimeoutSeconds = value; }
}
