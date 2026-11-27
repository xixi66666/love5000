package com.example.website.integration.health;

/**
 * 单个健康检查目标的配置项。
 *
 * <p>对应 {@code website.service-health.services} 下的一项，由 Spring Boot 绑定。
 * {@code name} 是稳定项目名，前端用 {@code data-health-service} 与之匹配；
 * {@code url} 是完整健康地址。字段可变是为了满足配置绑定，业务代码只读不写。</p>
 */
public class ServiceHealthDefinition {

    /** 稳定项目名，例如 {@code python-a}；同一份配置内必须唯一。 */
    private String name;
    /** 完整健康地址，只允许 http 或 https 且必须能解析出主机名。 */
    private String url;

    public ServiceHealthDefinition() {
    }

    public ServiceHealthDefinition(String name, String url) {
        this.name = name;
        this.url = url;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getUrl() {
        return url;
    }

    public void setUrl(String url) {
        this.url = url;
    }
}
