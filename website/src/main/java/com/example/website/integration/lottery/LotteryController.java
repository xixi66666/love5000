package com.example.website.integration.lottery;

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
 * 开奖数据操作台（{@code lottery}，端口 5179）的点击启动与状态查询入口。
 *
 * <p>属于 {@code website} 的 integration 适配层：只做 HTTP 入参与响应体组装、
 * 状态码映射，进程定位、拉起和健康轮询都由 {@link LotteryProcessManager} 负责，
 * 开奖数据与统计业务逻辑不得进入本类。</p>
 *
 * <p>仅当 {@code lottery.click-start.enabled=true}（默认开启）时才注册该 Bean，
 * 关闭后两个端点不存在。启动失败时把 {@link LotteryStartException} 的可读消息转成
 * HTTP 503 与统一错误体，首页卡片可直接展示原因。</p>
 */
@RestController
@RequestMapping("/api/services/lottery")
@ConditionalOnProperty(prefix = "lottery.click-start", name = "enabled", havingValue = "true")
public class LotteryController {

    private final LotteryProcessManager processManager;

    public LotteryController(LotteryProcessManager processManager) {
        this.processManager = processManager;
    }

    /**
     * 点击启动：已有健康实例直接复用，否则拉起 {@code python server.py --port 5179}
     * 并等待健康检查通过。
     *
     * @return 成功为 HTTP 200 与 {@code {success, status, url}}，{@code status} 为
     *         {@code started}（本次新拉起）或 {@code already-running}（复用已在线实例）；
     *         失败为 HTTP 503 与 {@code {success=false, message}}，{@code message}
     *         可直接展示给用户
     */
    @PostMapping("/start")
    public ResponseEntity<Object> start() {
        try {
            LotteryStartResult result = processManager.start();
            Map<String, Object> body = new HashMap<String, Object>();
            body.put("success", true);
            body.put("status", result.getStatus());
            body.put("url", result.getUrl());
            return ResponseEntity.ok(body);
        } catch (LotteryStartException exception) {
            Map<String, Object> error = new HashMap<String, Object>();
            error.put("success", false);
            error.put("message", exception.getMessage());
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(error);
        }
    }

    /**
     * 查询运行状态。
     *
     * <p>每次调用都会真实探测一次 {@code http://127.0.0.1:5179/api/health}，不读缓存，
     * 也不会触发启动；因此服务离线时只把 {@code running} 置为 {@code false}，
     * HTTP 状态码仍然是 200。</p>
     *
     * @return 固定包含 {@code success=true}、{@code running}（是否健康）和 {@code url}（入口地址）
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
