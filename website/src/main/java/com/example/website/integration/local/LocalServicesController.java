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

/**
 * 本机模型与视频服务的状态与操作入口。
 *
 * <p>属于 integration/local 的 Web 层，前缀 {@code /api/services/local}：
 * {@code GET /{service}/status} 返回状态，{@code GET /{service}/health} 供统一健康聚合
 * 探测（在线返回 200、离线返回 503，两者都带布尔 {@code success}），
 * {@code POST /{service}/{action}} 执行启动、加载、卸载、停止。业务判断全部委托给
 * {@link LocalServicesManager}，这里只做来源校验与异常映射。</p>
 *
 * <p>安全边界：只接受回环地址发起的请求，Host 必须是 localhost、127.0.0.1 或 ::1，
 * 带 Origin 的请求必须同源；写操作还要求自定义头 {@code X-Love530-Local: 1} 且拒绝
 * {@code Sec-Fetch-Site: cross-site}，防止任意网页借浏览器管理宿主机进程。
 * 校验失败一律返回 403，不透露具体是哪一项不通过。</p>
 */
@RestController
@RequestMapping("/api/services/local")
public class LocalServicesController {
    private final LocalServicesManager manager;

    public LocalServicesController(LocalServicesManager manager) {
        this.manager = manager;
    }

    /**
     * 读取单个本机服务的状态。
     *
     * @param service 服务标识：strata、aimedia 或 h3
     * @param request 用于来源校验
     * @return 固定字段的状态表：{@code success}、{@code service}、{@code running}、
     *         {@code url}、{@code loaded}、{@code modelState}，h3 另带 {@code installed}
     * @throws LocalServiceException 非本机来源（403）或服务标识未知（404）时抛出
     */
    @GetMapping("/{service}/status")
    public Map<String, Object> status(@PathVariable String service, HttpServletRequest request) {
        requireLocal(request, false);
        return manager.status(service);
    }

    /**
     * 统一健康聚合使用的探针。
     *
     * <p>复用状态查询并把 {@code success} 改成「是否在线」，因此在线返回 200、离线返回 503；
     * {@code service} 字段保持稳定，供巡检结果按名字匹配。</p>
     *
     * @param service 服务标识
     * @param request 用于来源校验
     * @return 状态体，HTTP 状态码随在线与否变化
     */
    @GetMapping("/{service}/health")
    public ResponseEntity<Map<String, Object>> health(@PathVariable String service, HttpServletRequest request) {
        Map<String, Object> body = status(service, request);
        boolean running = Boolean.TRUE.equals(body.get("running"));
        body.put("success", running);
        return ResponseEntity.status(running ? 200 : 503).body(body);
    }

    /**
     * 执行启动、加载、卸载或停止。
     *
     * @param service 服务标识
     * @param action  操作名，仅支持 start、load、unload、stop
     * @param request 用于来源校验
     * @return 操作后的最新状态，并附带 {@code action} 与结果 {@code message}
     * @throws LocalServiceException 来源非法（403）、服务不支持该操作（400）、
     *                               任务忙碌（409）或执行失败（503）时抛出
     */
    @PostMapping("/{service}/{action}")
    public Map<String, Object> action(@PathVariable String service, @PathVariable String action,
                                     HttpServletRequest request) {
        requireLocal(request, true);
        return manager.action(service, action);
    }

    /**
     * 校验请求确实来自宿主机的同源页面。
     *
     * <p>三道条件：远端地址必须是回环地址；Host 必须是 localhost、127.0.0.1 或 ::1
     * （含 IPv6 的中括号形式），避免请求被解析到非预期主机；带 Origin 时必须与当前
     * scheme、主机、端口完全一致。写操作额外要求 {@code X-Love530-Local: 1}，
     * 并拒绝 {@code Sec-Fetch-Site: cross-site} 的跨站提交。</p>
     *
     * @param request  当前请求
     * @param mutation 是否为写操作
     * @throws LocalServiceException 任一条件不满足时抛出 403
     */
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

    /**
     * 把业务异常映射成统一的失败响应。
     *
     * <p>响应体固定为 {@code success=false} 加可读 {@code message}，HTTP 状态码取自异常
     * 自带的建议值，因此控制器方法不需要自己处理错误分支。</p>
     *
     * @param exception 业务异常
     * @return 失败响应，状态码由异常决定
     */
    @ExceptionHandler(LocalServiceException.class)
    public ResponseEntity<Map<String, Object>> error(LocalServiceException exception) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("success", false);
        body.put("message", exception.getMessage());
        return ResponseEntity.status(exception.getStatus()).body(body);
    }
}
