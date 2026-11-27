package com.example.imagetemplate.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 统一健康检查端点。
 *
 * <p>只返回固定结构 {@code {"success": true, "service": "imagetemplate"}}，
 * 不读取模板资源，也不调用 OpenAI。因此即使图片密钥缺失或大库降级为
 * {@code DEGRADED}，该端点仍应保持 200，供 website 的 {@code ServiceHealthChecker}
 * 判断进程是否存活。</p>
 *
 * <p>{@code service} 是跨服务聚合的稳定标识，不要随端口或部署环境改名。</p>
 */
@RestController
@RequestMapping("/api")
public class HealthController {

    /**
     * 返回本服务的存活状态。
     *
     * <p>用 {@link LinkedHashMap} 固定字段顺序（{@code success} 在前、{@code service} 在后），
     * 方便排查时直接阅读原始响应。</p>
     *
     * @return 含 {@code success=true} 与 {@code service=imagetemplate} 的响应体
     */
    @GetMapping("/health")
    public Map<String, Object> health() {
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("success", true);
        response.put("service", "imagetemplate");
        return response;
    }
}

