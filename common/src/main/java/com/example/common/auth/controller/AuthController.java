package com.example.common.auth.controller;

import com.example.common.auth.dto.AuthLoginRequest;
import com.example.common.auth.dto.AuthRegisterRequest;
import com.example.common.auth.model.AuthUserPrincipal;
import com.example.common.auth.service.AuthService;
import org.springframework.boot.autoconfigure.condition.ConditionalOnBean;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.util.HashMap;
import java.util.Map;

/**
 * 通用认证 HTTP 入口，对外暴露 {@code /api/auth} 下的注册、登录、登出与当前用户查询。
 *
 * <p>属于 Web 层，只负责入参绑定与响应组装；用户名规范化、密码策略、会话写入等规则
 * 全部在 {@code AuthService} 中实现，异常由 {@code AuthExceptionHandler} 统一转成 HTTP 状态码。</p>
 *
 * <p>成功响应固定包含 {@code success=true} 与 {@code message}，注册和登录还会带上 {@code user}；
 * 查询当前用户时即使未登录也返回 200，只是 {@code user} 为 {@code null}，
 * 便于前端把它当作状态探测而不是错误处理。</p>
 */
@RestController
@RequestMapping("/api/auth")
@ConditionalOnBean(AuthService.class)
public class AuthController {

    private final AuthService authService;

    /**
     * 构造控制器；服务实现由自动配置注入，缺失时该 Bean 不会被创建。
     *
     * @param authService 认证服务
     */
    public AuthController(AuthService authService) {
        this.authService = authService;
    }

    /**
     * 注册新用户，并在成功后直接建立登录会话。
     *
     * @param authRequest 注册请求体，用户名与密码规则由服务层校验
     * @param request 当前请求，用于写入新的 Session
     * @return {@code success=true}、提示语与新用户主体
     * @throws com.example.common.auth.exception.AuthException 用户名重复或用户名、密码不合规时抛出，由异常处理器转为 400
     */
    @PostMapping("/register")
    public Map<String, Object> register(@RequestBody AuthRegisterRequest authRequest, HttpServletRequest request) {
        AuthUserPrincipal user = authService.register(authRequest, request);
        return userResponse("Register succeeded", user);
    }

    /**
     * 校验凭据并建立登录会话。
     *
     * @param authRequest 登录请求体，密码为明文
     * @param request 当前请求，用于写入新的 Session
     * @return {@code success=true}、提示语与登录用户主体
     * @throws com.example.common.auth.exception.AuthException 用户不存在、密码错误或账号被禁用时抛出，统一为 401 且不区分具体原因
     */
    @PostMapping("/login")
    public Map<String, Object> login(@RequestBody AuthLoginRequest authRequest, HttpServletRequest request) {
        AuthUserPrincipal user = authService.login(authRequest, request);
        return userResponse("Login succeeded", user);
    }

    /**
     * 注销当前会话。
     *
     * <p>幂等：原本就没有会话时同样返回成功，避免前端重复点击报错。</p>
     *
     * @param request 当前请求
     * @param response 当前响应，交由服务层处理（当前实现不改动 Cookie）
     * @return {@code success=true} 与提示语
     */
    @PostMapping("/logout")
    public Map<String, Object> logout(HttpServletRequest request, HttpServletResponse response) {
        authService.logout(request, response);
        Map<String, Object> result = new HashMap<String, Object>();
        result.put("success", true);
        result.put("message", "Logout succeeded");
        return result;
    }

    /**
     * 查询当前登录用户。
     *
     * @param request 当前请求
     * @return {@code success} 恒为 {@code true}；未登录时 {@code user} 为 {@code null}
     */
    @GetMapping("/me")
    public Map<String, Object> me(HttpServletRequest request) {
        Map<String, Object> result = new HashMap<String, Object>();
        result.put("success", true);
        result.put("user", authService.currentUser(request).orElse(null));
        return result;
    }

    /**
     * 组装注册与登录共用的成功响应，保证两处结构一致。
     *
     * @param message 面向用户的提示语
     * @param user 登录主体，不应为 {@code null}
     * @return 含 {@code success}、{@code message} 与 {@code user} 的响应体
     */
    private Map<String, Object> userResponse(String message, AuthUserPrincipal user) {
        Map<String, Object> result = new HashMap<String, Object>();
        result.put("success", true);
        result.put("message", message);
        result.put("user", user);
        return result;
    }
}
