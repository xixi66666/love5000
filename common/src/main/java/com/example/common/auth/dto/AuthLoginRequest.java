package com.example.common.auth.dto;

/**
 * 登录接口 {@code POST /api/auth/login} 的请求体。
 *
 * <p>仅作为 JSON 反序列化载体：用户名的去空格、转小写与凭据比对全部由
 * {@code AuthServiceImpl} 完成，所以这里不加格式校验注解，
 * 避免校验失败绕过统一的 {@code AuthException} 响应结构。</p>
 *
 * <p>{@code password} 是明文传输载体，只在服务端参与 BCrypt 比对，
 * 不应写入日志、响应或任何持久化存储。</p>
 */
public class AuthLoginRequest {

    private String username;

    private String password;

    public String getUsername() {
        return username;
    }

    public void setUsername(String username) {
        this.username = username;
    }

    public String getPassword() {
        return password;
    }

    public void setPassword(String password) {
        this.password = password;
    }
}
