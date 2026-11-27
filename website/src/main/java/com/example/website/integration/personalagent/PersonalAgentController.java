package com.example.website.integration.personalagent;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.servlet.http.HttpServletRequest;
import java.net.InetAddress;
import java.net.URI;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 个人长期资料库（{@code personal-agent}，端口 5178）的点击启动与状态查询入口。
 *
 * <p>属于 website 的 integration 适配层，03 Deep Woods 的「个人资料库」卡片调用
 * {@code POST /api/services/personal-agent/start}；本类只做本机来源校验、状态码映射和
 * 响应体组装，进程管理与健康探测交给 {@link PersonalAgentProcessManager}。</p>
 *
 * <p>与另外几个点击启动端点不同，这里额外要求请求来自本机浏览器：被拉动的是完整
 * Java 进程，若允许任意来源调用，等于把本机进程启动能力暴露给任何网页。校验分三层：
 * 回环地址与 {@code localhost}、{@code 127.0.0.1}、{@code ::1} 主机名；{@code Host}
 * 与 {@code Origin} 必须与当前站点同源；启动这类写操作还要求同源或非浏览器发起的
 * {@code Sec-Fetch-Site}。校验不通过一律 HTTP 403，且不暴露进程细节。</p>
 *
 * <p>响应体用 {@link LinkedHashMap} 保证 JSON 字段顺序稳定，便于前端与调试时直接阅读。</p>
 */
@RestController
@RequestMapping("/api/services/personal-agent")
@ConditionalOnProperty(prefix = "personal-agent.click-start", name = "enabled", havingValue = "true")
public class PersonalAgentController {

    private final PersonalAgentProcessManager processManager;

    public PersonalAgentController(PersonalAgentProcessManager processManager) {
        this.processManager = processManager;
    }

    /**
     * 启动或复用个人资料库。
     *
     * <p>先做本机来源校验，再委托 {@link PersonalAgentProcessManager#start()}；
     * 校验失败不触碰进程，避免跨站请求探测本机运行状态。</p>
     *
     * @param request 当前请求，用于回环地址、{@code Host}、{@code Origin}
     *                与 {@code Sec-Fetch-Site} 校验
     * @return 成功为 HTTP 200 与 {@code {success, status, url}}；非本机请求为 HTTP 403；
     *         启动失败（尚未构建 jar、端口被占用、超时未就绪）为 HTTP 503 与
     *         {@code {success=false, message}}
     */
    @PostMapping("/start")
    public ResponseEntity<Map<String, Object>> start(HttpServletRequest request) {
        if (!isLocal(request, true)) {
            return error(403, "请在本机浏览器中通过 love530 首页启动个人资料库");
        }
        try {
            PersonalAgentStartResult result = processManager.start();
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("success", true);
            body.put("status", result.getStatus());
            body.put("url", result.getUrl());
            return ResponseEntity.ok(body);
        } catch (PersonalAgentStartException exception) {
            return error(503, exception.getMessage());
        }
    }

    /**
     * 查询个人资料库运行状态。
     *
     * @param request 当前请求，同样要求本机来源；该端点不改状态，但仍拒绝跨站读取
     * @return 本机请求为 HTTP 200 与 {@code {success, running, url}}，否则 HTTP 403
     */
    @GetMapping("/status")
    public ResponseEntity<Map<String, Object>> status(HttpServletRequest request) {
        if (!isLocal(request, false)) {
            return error(403, "请在本机浏览器中查看个人资料库 状态");
        }
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("success", true);
        body.put("running", processManager.isRunning());
        body.put("url", processManager.appUrl());
        return ResponseEntity.ok(body);
    }

    /**
     * 判断请求是否来自本机同源浏览器。
     *
     * <p>判定顺序：远端地址必须是回环地址且请求主机名为 {@code localhost}、
     * {@code 127.0.0.1} 或 {@code ::1}；带 {@code Host} 头时要求它与「当前协议 + 端口」
     * 同源；带 {@code Origin} 头时要求同源。{@code mutation=true}（启动）时再要求
     * {@code Sec-Fetch-Site} 为 {@code same-origin} 或 {@code none}，并且必须同时具备
     * 同源 {@code Origin}，以挡掉跨站表单提交式的 CSRF。任何解析异常都按非本机处理，
     * 失败即拒绝。</p>
     *
     * @param request  当前请求
     * @param mutation 是否为改变状态的写操作；只读状态查询传 {@code false}
     * @return {@code true} 表示可以继续处理
     */
    private boolean isLocal(HttpServletRequest request, boolean mutation) {
        try {
            String host = request.getServerName();
            if (!InetAddress.getByName(request.getRemoteAddr()).isLoopbackAddress()
                    || !("localhost".equalsIgnoreCase(host) || "127.0.0.1".equals(host)
                    || "::1".equals(host) || "[::1]".equals(host))) {
                return false;
            }
            String hostHeader = request.getHeader("Host");
            if (hostHeader != null && !matchesOrigin(request, request.getScheme() + "://" + hostHeader)) {
                return false;
            }
            String origin = request.getHeader("Origin");
            if (origin != null && !matchesOrigin(request, origin)) {
                return false;
            }
            if (mutation) {
                String fetchSite = request.getHeader("Sec-Fetch-Site");
                if (fetchSite != null && !"same-origin".equals(fetchSite) && !"none".equals(fetchSite)) {
                    return false;
                }
                if (origin == null && !"same-origin".equals(fetchSite)) {
                    return false;
                }
            }
            return true;
        } catch (Exception exception) {
            return false;
        }
    }

    /**
     * 判断 {@code origin} 与当前请求是否同源。
     *
     * <p>逐项比较协议、主机（不区分大小写，IPv6 去掉方括号）与端口（缺省按协议补
     * 80/443），并要求 URI 不含 userinfo、查询串、片段和路径，避免
     * {@code http://127.0.0.1:8080@evil.example} 这类借用 userinfo 伪装同源的写法通过。</p>
     *
     * @param request 当前请求
     * @param origin  待比较的来源字符串，例如 {@code http://127.0.0.1:8080}
     * @return {@code true} 表示同源
     * @throws Exception 来源字符串不是合法 URI；调用方 {@link #isLocal} 会按非本机处理
     */
    private boolean matchesOrigin(HttpServletRequest request, String origin) throws Exception {
        URI uri = new URI(origin);
        int port = uri.getPort() < 0 ? ("https".equals(uri.getScheme()) ? 443 : 80) : uri.getPort();
        String host = uri.getHost();
        String requestHost = request.getServerName();
        if (host != null && host.startsWith("[") && host.endsWith("]")) {
            host = host.substring(1, host.length() - 1);
        }
        if (requestHost.startsWith("[") && requestHost.endsWith("]")) {
            requestHost = requestHost.substring(1, requestHost.length() - 1);
        }
        return request.getScheme().equals(uri.getScheme()) && requestHost.equalsIgnoreCase(host)
                && request.getServerPort() == port && uri.getUserInfo() == null
                && uri.getRawQuery() == null && uri.getFragment() == null
                && (uri.getPath() == null || uri.getPath().isEmpty());
    }

    /**
     * 组装失败响应体。
     *
     * @param status  HTTP 状态码，403 表示非本机访问，503 表示启动失败
     * @param message 面向用户的中文原因
     * @return 带 {@code success=false} 与 {@code message} 的响应
     */
    private ResponseEntity<Map<String, Object>> error(int status, String message) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("success", false);
        body.put("message", message);
        return ResponseEntity.status(status).body(body);
    }
}
