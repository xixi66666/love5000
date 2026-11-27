package com.example.website.integration.health;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 统一健康检查 HTTP 入口。
 *
 * <p>属于 integration/health 的 Web 层，只暴露 {@code GET /api/services/health}，
 * 把最近一次巡检快照原样返回给首页与本机服务管理页；不在这里做实时探测，
 * 避免每次刷新页面都去访问 11 个子服务。</p>
 *
 * <p>响应恒为 HTTP 200：{@code success=true} 表示巡检已生成汇总（全部离线仍可为
 * true），{@code healthy} 才表示所有目标都在线。若服务刚启动且尚无快照，
 * 读取会同步等待一轮探测完成。</p>
 */
@RestController
@RequestMapping("/api/services")
public class ServiceHealthController {

    private final ServiceHealthMonitor monitor;

    public ServiceHealthController(ServiceHealthMonitor monitor) {
        this.monitor = monitor;
    }

    /**
     * 读取最近一次巡检结果。
     *
     * @return 聚合快照，字段为 {@code success}、{@code healthy} 与 {@code services}
     */
    @GetMapping("/health")
    public ServiceHealthSummary health() {
        return monitor.snapshot();
    }
}
