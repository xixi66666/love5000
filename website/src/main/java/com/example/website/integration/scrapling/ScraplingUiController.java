package com.example.website.integration.scrapling;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.Map;

/**
 * Scrapling 抓取工坊（{@code scrapling-ui}，端口 5176）的点击启动与状态查询入口。
 *
 * <p>属于 website 的 integration 适配层，首页 Dock 卡片调用
 * {@code POST /api/services/scrapling-ui/start}；本类只做响应体组装与 HTTP 状态码映射，
 * 目录校验、Python 解释器选择、进程拉起和健康轮询都在
 * {@link ScraplingUiProcessManager} 内，抓取业务逻辑不进入 Java。</p>
 *
 * <p>启动失败时返回 HTTP 503 与可读原因；状态查询始终返回 HTTP 200，由
 * {@code running} 字段表达在线与否。该端点不做本机来源校验，依赖首页同源调用。</p>
 */
@RestController
@RequestMapping("/api/services/scrapling-ui")
@ConditionalOnProperty(prefix = "scrapling-ui.click-start", name = "enabled", havingValue = "true")
public class ScraplingUiController {

    private final ScraplingUiProcessManager processManager;

    public ScraplingUiController(ScraplingUiProcessManager processManager) {
        this.processManager = processManager;
    }

    /**
     * 启动或复用 Scrapling 抓取工坊。
     *
     * @return 成功为 HTTP 200 与 {@code {success, status, url}}，{@code status} 取
     *         {@code started} 或 {@code already-running}；失败为 HTTP 503 与
     *         {@code {success=false, message}}，{@code message} 可直接展示给用户
     */
    @PostMapping("/start")
    public ResponseEntity<Object> start() {
        try {
            ScraplingUiStartResult result = processManager.start();
            Map<String, Object> body = new HashMap<String, Object>();
            body.put("success", true);
            body.put("status", result.getStatus());
            body.put("url", result.getUrl());
            return ResponseEntity.ok(body);
        } catch (ScraplingUiStartException exception) {
            Map<String, Object> error = new HashMap<String, Object>();
            error.put("success", false);
            error.put("message", exception.getMessage());
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(error);
        }
    }

    /**
     * 查询运行状态。
     *
     * <p>每次调用真实探测一次 {@code http://127.0.0.1:5176/api/health}，不读缓存，
     * 也不会触发启动。</p>
     *
     * @return {@code {success=true, running, url}}；服务离线时 {@code running=false}，
     *         HTTP 状态码仍为 200
     */
    @GetMapping("/status")
    public Map<String, Object> status() {
        Map<String, Object> body = new HashMap<String, Object>();
        body.put("success", true);
        body.put("running", processManager.isRunning());
        body.put("url", processManager.appUrl());
        return body;
    }
}
