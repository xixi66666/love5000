package com.example.website.integration.health;

import java.util.List;

/**
 * 一轮健康巡检的聚合结果，也是 {@code GET /api/services/health} 的响应体。
 *
 * <p>两个布尔字段语义不同：{@code success} 表示巡检本身是否生成了汇总，
 * 即使所有目标离线也可以为 {@code true}；{@code healthy} 才表示是否所有目标都在线。
 * {@code services} 按配置顺序保存每个目标的明细。</p>
 */
public class ServiceHealthSummary {

    private final boolean success;
    private final boolean healthy;
    private final List<ServiceHealthResult> services;

    /**
     * 构造聚合结果。
     *
     * @param success  是否成功生成汇总
     * @param healthy  是否所有目标都在线
     * @param services 按配置顺序排列的单目标结果，可为空列表但不应为 {@code null}
     */
    public ServiceHealthSummary(boolean success,
                                boolean healthy,
                                List<ServiceHealthResult> services) {
        this.success = success;
        this.healthy = healthy;
        this.services = services;
    }

    public boolean isSuccess() {
        return success;
    }

    public boolean isHealthy() {
        return healthy;
    }

    public List<ServiceHealthResult> getServices() {
        return services;
    }
}
