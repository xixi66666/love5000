package com.example.website.integration.health;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

import javax.annotation.PostConstruct;
import java.net.URI;
import java.net.URISyntaxException;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * 统一健康巡检的配置项，前缀 {@code website.service-health}。
 *
 * <p>把「检查清单、超时、频率」全部外置到 application.yml：新增服务只需追加一项配置，
 * 不用改 Java 代码。默认值：连接超时 2000 毫秒、读取超时 3000 毫秒、巡检间隔
 * 1800000 毫秒（30 分钟）、定时巡检开启。默认清单为 8 个独立服务加 strata、aimedia、
 * h3 三个本机适配，共 11 个目标。</p>
 *
 * <p>{@link #validate()} 在装配完成后立即校验，让配置错误在启动期暴露，
 * 而不是等到运行时才发现某个目标永远离线。</p>
 */
@Component
@ConfigurationProperties(prefix = "website.service-health")
public class ServiceHealthProperties {

    /** 连接超时，单位毫秒；默认 2000，过短会把冷启动中的子服务误判为离线。 */
    private int connectTimeoutMs = 2000;
    /** 读取超时，单位毫秒；默认 3000，需覆盖服务端组装健康 JSON 的时间。 */
    private int readTimeoutMs = 3000;
    /** 巡检间隔，单位毫秒；默认 30 分钟，首页与管理页的刷新节奏与之对齐。 */
    private long checkIntervalMs = 30 * 60 * 1000L;
    /** 是否注册后台定时巡检；单元测试设为 false，避免访问真实服务。 */
    private boolean scheduledEnabled = true;
    /** 目标清单，顺序即聚合响应中的顺序，与首页入口顺序保持一致。 */
    private List<ServiceHealthDefinition> services = new ArrayList<>();

    /**
     * 装配完成后校验配置，发现非法值立即失败。
     *
     * <p>检查项：巡检间隔、连接超时、读取超时都必须为正数；每个目标必须有非空名称
     * （顺带去掉首尾空白）、名称不得重复、URL 必须合法。启动期失败比运行期静默降级更容易
     * 定位配置错误。</p>
     *
     * @throws IllegalStateException 任一检查项不满足时抛出
     */
    @PostConstruct
    public void validate() {
        if (checkIntervalMs <= 0) {
            throw new IllegalStateException("website.service-health.check-interval-ms must be positive");
        }
        if (connectTimeoutMs <= 0) {
            throw new IllegalStateException("website.service-health.connect-timeout-ms must be positive");
        }
        if (readTimeoutMs <= 0) {
            throw new IllegalStateException("website.service-health.read-timeout-ms must be positive");
        }

        Set<String> names = new HashSet<>();
        for (int i = 0; i < services.size(); i++) {
            ServiceHealthDefinition definition = services.get(i);
            if (definition == null || isBlank(definition.getName())) {
                throw new IllegalStateException("website.service-health service[" + i + "] name must not be blank");
            }
            String name = definition.getName().trim();
            definition.setName(name);
            if (!names.add(name)) {
                throw new IllegalStateException("duplicate service name: " + name);
            }
            validateUrl(name, definition.getUrl());
        }
    }

    /**
     * 校验健康地址是否为可用的 HTTP 地址。
     *
     * <p>只接受 http 或 https，且必须能解析出主机名；路径、端口和查询串允许存在，
     * 便于接入带固定前缀的适配接口。错误提示只带目标名称，不回显原始 URL。</p>
     *
     * @param name 目标名称，用于拼接错误提示
     * @param url  待校验地址
     * @throws IllegalStateException 地址为空、无法解析或协议不受支持时抛出
     */
    private void validateUrl(String name, String url) {
        if (isBlank(url)) {
            throw new IllegalStateException("service " + name + " has an invalid health URL");
        }
        try {
            URI uri = new URI(url);
            String scheme = uri.getScheme();
            String normalizedScheme = scheme == null ? "" : scheme.toLowerCase(Locale.ROOT);
            if ((!"http".equals(normalizedScheme) && !"https".equals(normalizedScheme))
                    || isBlank(uri.getHost())) {
                throw new IllegalStateException("service " + name + " has an invalid health URL");
            }
        } catch (URISyntaxException e) {
            throw new IllegalStateException("service " + name + " has an invalid health URL");
        }
    }

    private boolean isBlank(String value) {
        return value == null || value.trim().isEmpty();
    }

    public int getConnectTimeoutMs() {
        return connectTimeoutMs;
    }

    public void setConnectTimeoutMs(int connectTimeoutMs) {
        this.connectTimeoutMs = connectTimeoutMs;
    }

    public int getReadTimeoutMs() {
        return readTimeoutMs;
    }

    public void setReadTimeoutMs(int readTimeoutMs) {
        this.readTimeoutMs = readTimeoutMs;
    }

    public List<ServiceHealthDefinition> getServices() {
        return services;
    }

    public long getCheckIntervalMs() {
        return checkIntervalMs;
    }

    public void setCheckIntervalMs(long checkIntervalMs) {
        this.checkIntervalMs = checkIntervalMs;
    }

    public boolean isScheduledEnabled() {
        return scheduledEnabled;
    }

    public void setScheduledEnabled(boolean scheduledEnabled) {
        this.scheduledEnabled = scheduledEnabled;
    }

    public void setServices(List<ServiceHealthDefinition> services) {
        this.services = services == null ? new ArrayList<>() : services;
    }
}
