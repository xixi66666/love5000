package com.ycxandwuqian.love.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 统一健康检查端点。
 *
 * <p>暴露 {@code GET /api/health}，返回固定的 {@code {"success":true,"service":"lovestory"}}。
 * 本方法不查询 MySQL、不探测 OSS、不依赖任何注入的 Bean，因此它表达的是"进程已就绪"，
 * 而不是"下游依赖全部可用"。</p>
 *
 * <p>上游 {@code website} 的 {@code ServiceHealthChecker} 以 HTTP 2xx 且顶层
 * {@code success=true} 作为单个目标的健康判据：数据库或对象存储故障时本服务仍会显示在线，
 * 这样聚合页不会因为一台远程 MySQL 抖动就把整个相册标记为不可用。</p>
 */
@RestController
@RequestMapping("/api")
public class HealthController {

    /**
     * 返回服务存活状态。
     *
     * <p>使用 {@link LinkedHashMap} 而非 {@code HashMap}，是为了让 JSON 字段顺序稳定为
     * {@code success}、{@code service}，便于聚合方日志与人工排查时直接比对。</p>
     *
     * @return 恒为成功语义的固定响应体，不反映数据库或 OSS 的真实状态
     */
    @GetMapping("/health")
    public Map<String, Object> health() {
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("success", true);
        response.put("service", "lovestory");
        return response;
    }
}
