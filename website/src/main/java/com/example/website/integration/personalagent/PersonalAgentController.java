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

@RestController
@RequestMapping("/api/services/personal-agent")
@ConditionalOnProperty(prefix = "personal-agent.click-start", name = "enabled", havingValue = "true")
public class PersonalAgentController {

    private final PersonalAgentProcessManager processManager;

    public PersonalAgentController(PersonalAgentProcessManager processManager) {
        this.processManager = processManager;
    }

    @PostMapping("/start")
    public ResponseEntity<Map<String, Object>> start(HttpServletRequest request) {
        if (!isLocal(request, true)) {
            return error(403, "请在本机浏览器中通过 love530 首页启动个人 Agent");
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

    @GetMapping("/status")
    public ResponseEntity<Map<String, Object>> status(HttpServletRequest request) {
        if (!isLocal(request, false)) {
            return error(403, "请在本机浏览器中查看个人 Agent 状态");
        }
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("success", true);
        body.put("running", processManager.isRunning());
        body.put("url", processManager.appUrl());
        return ResponseEntity.ok(body);
    }

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

    private ResponseEntity<Map<String, Object>> error(int status, String message) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("success", false);
        body.put("message", message);
        return ResponseEntity.status(status).body(body);
    }
}
