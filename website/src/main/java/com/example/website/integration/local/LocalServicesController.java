package com.example.website.integration.local;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.servlet.http.HttpServletRequest;
import java.net.InetAddress;
import java.net.URI;
import java.util.LinkedHashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/services/local")
public class LocalServicesController {
    private final LocalServicesManager manager;

    public LocalServicesController(LocalServicesManager manager) {
        this.manager = manager;
    }

    @GetMapping("/{service}/status")
    public Map<String, Object> status(@PathVariable String service, HttpServletRequest request) {
        requireLocal(request, false);
        return manager.status(service);
    }

    @GetMapping("/{service}/health")
    public ResponseEntity<Map<String, Object>> health(@PathVariable String service, HttpServletRequest request) {
        Map<String, Object> body = status(service, request);
        boolean running = Boolean.TRUE.equals(body.get("running"));
        body.put("success", running);
        return ResponseEntity.status(running ? 200 : 503).body(body);
    }

    @PostMapping("/{service}/{action}")
    public Map<String, Object> action(@PathVariable String service, @PathVariable String action,
                                     HttpServletRequest request) {
        requireLocal(request, true);
        return manager.action(service, action);
    }

    private void requireLocal(HttpServletRequest request, boolean mutation) {
        try {
            String host = request.getServerName();
            if (!InetAddress.getByName(request.getRemoteAddr()).isLoopbackAddress()
                    || !("localhost".equalsIgnoreCase(host) || "127.0.0.1".equals(host)
                    || "::1".equals(host) || "[::1]".equals(host))) {
                throw new IllegalArgumentException();
            }
            String origin = request.getHeader("Origin");
            if (origin != null) {
                URI uri = new URI(origin);
                int port = uri.getPort() < 0 ? ("https".equals(uri.getScheme()) ? 443 : 80) : uri.getPort();
                if (!request.getScheme().equals(uri.getScheme()) || !host.equalsIgnoreCase(uri.getHost())
                        || request.getServerPort() != port) throw new IllegalArgumentException();
            }
            if (mutation && (!"1".equals(request.getHeader("X-Love530-Local"))
                    || "cross-site".equals(request.getHeader("Sec-Fetch-Site")))) {
                throw new IllegalArgumentException();
            }
        } catch (Exception exception) {
            throw new LocalServiceException(403, "请在主机本机浏览器中通过 love530 管理这些服务");
        }
    }

    @ExceptionHandler(LocalServiceException.class)
    public ResponseEntity<Map<String, Object>> error(LocalServiceException exception) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("success", false);
        body.put("message", exception.getMessage());
        return ResponseEntity.status(exception.getStatus()).body(body);
    }
}
