package com.example.common.auth.web;

import com.example.common.auth.annotation.AuthRequired;
import com.example.common.auth.service.AuthService;
import org.springframework.web.method.HandlerMethod;
import org.springframework.web.servlet.HandlerInterceptor;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

/**
 * 基于 {@code AuthRequired} 注解的会话校验拦截器。
 *
 * <p>虽然被注册在全部路径上，但只有目标处理器是 {@code HandlerMethod}、且方法或所在类标注了
 * {@code AuthRequired} 时才真正校验登录态；静态资源等非方法处理器直接放行。
 * 未标注注解的接口完全不做鉴权，所以这条链路只提供「按需登录校验」，
 * 不是全局权限控制，需要保护的新接口必须显式标注。</p>
 *
 * <p>校验失败由 {@code AuthService#requireCurrentUser} 抛出 {@code AuthException}，
 * 再经 {@code AuthExceptionHandler} 转成 401；拦截器自身不写响应体，也不返回 false。</p>
 */
public class AuthInterceptor implements HandlerInterceptor {

    private final AuthService authService;

    /**
     * 构造拦截器。
     *
     * @param authService 认证服务，用于校验会话中的登录态
     */
    public AuthInterceptor(AuthService authService) {
        this.authService = authService;
    }

    /**
     * 在处理器执行前校验登录态。
     *
     * @param request 当前请求，用于读取会话
     * @param response 当前响应，本实现不直接写入
     * @param handler 目标处理器；不是 {@code HandlerMethod} 时直接放行
     * @return 恒为 {@code true}；未登录时以抛出异常的方式中断请求，交给异常处理器响应
     * @throws com.example.common.auth.exception.AuthException 目标方法或所在类要求登录、
     *     而当前会话无有效用户时抛出
     */
    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) {
        if (!(handler instanceof HandlerMethod)) {
            return true;
        }
        HandlerMethod handlerMethod = (HandlerMethod) handler;
        boolean authRequired = handlerMethod.hasMethodAnnotation(AuthRequired.class)
                || handlerMethod.getBeanType().isAnnotationPresent(AuthRequired.class);
        if (authRequired) {
            authService.requireCurrentUser(request);
        }
        return true;
    }
}
