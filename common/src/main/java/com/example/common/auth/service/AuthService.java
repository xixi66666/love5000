package com.example.common.auth.service;

import com.example.common.auth.dto.AuthLoginRequest;
import com.example.common.auth.dto.AuthRegisterRequest;
import com.example.common.auth.model.AuthUserPrincipal;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.util.Optional;

/**
 * 登录态服务契约，负责注册、登录、注销与当前用户解析。
 *
 * <p>方法直接接收 Servlet 的 {@code HttpServletRequest} 与 {@code HttpServletResponse}，
 * 因为登录态保存在 {@code HttpSession} 中，实现需要读写会话并处理会话固定问题；
 * 非 Web 场景调用时需自行提供可用的请求对象。</p>
 *
 * <p>失败语义统一为抛出 {@code AuthException}，由 Web 层转换成 HTTP 状态码，
 * 调用方无需自行区分「参数不合规」与「凭据错误」的响应格式。</p>
 */
public interface AuthService {

    /**
     * 注册新用户并建立登录会话。
     *
     * @param authRequest 注册请求，用户名与密码为必填
     * @param request 当前请求，成功后写入新的 Session
     * @return 新用户的会话主体
     * @throws com.example.common.auth.exception.AuthException 参数不合规或用户名重复时抛出 400
     */
    AuthUserPrincipal register(AuthRegisterRequest authRequest, HttpServletRequest request);

    /**
     * 校验凭据并建立登录会话。
     *
     * @param authRequest 登录请求，密码为明文
     * @param request 当前请求，成功后写入新的 Session
     * @return 登录用户的会话主体
     * @throws com.example.common.auth.exception.AuthException 凭据无效或账号被禁用时抛出 401
     */
    AuthUserPrincipal login(AuthLoginRequest authRequest, HttpServletRequest request);

    /**
     * 注销当前会话；没有会话时直接返回，保证重复调用安全。
     *
     * @param request 当前请求
     * @param response 当前响应，预留给需要清理 Cookie 的实现
     */
    void logout(HttpServletRequest request, HttpServletResponse response);

    /**
     * 读取当前登录用户。
     *
     * @param request 当前请求
     * @return 已登录时返回会话主体，否则返回空 Optional
     */
    Optional<AuthUserPrincipal> currentUser(HttpServletRequest request);

    /**
     * 读取当前登录用户，未登录即失败。
     *
     * @param request 当前请求
     * @return 当前登录用户，保证非空
     * @throws com.example.common.auth.exception.AuthException 未登录时抛出 401
     */
    AuthUserPrincipal requireCurrentUser(HttpServletRequest request);
}
