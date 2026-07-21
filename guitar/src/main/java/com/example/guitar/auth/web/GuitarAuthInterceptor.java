package com.example.guitar.auth.web;

import com.example.guitar.auth.model.GuitarUserPrincipal;
import com.example.guitar.auth.service.GuitarAuthService;
import com.example.guitar.web.GuitarApiException;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.util.UrlPathHelper;
import org.springframework.web.servlet.HandlerInterceptor;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import javax.servlet.http.HttpSession;
import java.util.Locale;
import java.util.Optional;

@Component
public class GuitarAuthInterceptor implements HandlerInterceptor {

    private static final UrlPathHelper URL_PATH_HELPER = createUrlPathHelper();

    private final GuitarAuthService authService;
    private final CsrfTokenService csrfTokenService;

    public GuitarAuthInterceptor(GuitarAuthService authService, CsrfTokenService csrfTokenService) {
        this.authService = authService;
        this.csrfTokenService = csrfTokenService;
    }

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) {
        String method = request.getMethod().toUpperCase(Locale.ROOT);
        if ("OPTIONS".equals(method)) {
            return true;
        }
        boolean writeRequest = isWriteRequest(method);
        if (writeRequest) {
            HttpSession session = request.getSession(false);
            if (!csrfTokenService.isValid(session, request.getHeader(CsrfTokenService.HEADER_NAME))) {
                throw new GuitarApiException(HttpStatus.FORBIDDEN, "CSRF_INVALID",
                        "CSRF Token 缺失或无效");
            }
        }

        String path = requestPath(request);
        boolean adminRequired = matchesPrefix(path, "/api/admin");
        boolean loginRequired = adminRequired
                || matchesPrefix(path, "/api/users")
                || matchesPrefix(path, "/api/favorite-folders")
                || (writeRequest && matchesPrefix(path, "/api/sheets"));
        if (!loginRequired) {
            return true;
        }

        Optional<GuitarUserPrincipal> principal = authService.currentSession(request);
        if (!principal.isPresent()) {
            throw new GuitarApiException(HttpStatus.UNAUTHORIZED, "AUTH_REQUIRED", "请先登录");
        }
        if (adminRequired && !"ADMIN".equals(principal.get().getRole())) {
            throw new GuitarApiException(HttpStatus.FORBIDDEN, "ADMIN_REQUIRED", "需要管理员权限");
        }
        return true;
    }

    private boolean isWriteRequest(String method) {
        return "POST".equals(method)
                || "PUT".equals(method)
                || "PATCH".equals(method)
                || "DELETE".equals(method);
    }

    private String requestPath(HttpServletRequest request) {
        String lookupPath = URL_PATH_HELPER.getLookupPathForRequest(request);
        return URL_PATH_HELPER.removeSemicolonContent(lookupPath);
    }

    private static UrlPathHelper createUrlPathHelper() {
        UrlPathHelper pathHelper = new UrlPathHelper();
        pathHelper.setRemoveSemicolonContent(true);
        pathHelper.setUrlDecode(true);
        return pathHelper;
    }

    private boolean matchesPrefix(String path, String prefix) {
        return path.equals(prefix) || path.startsWith(prefix + "/");
    }
}
