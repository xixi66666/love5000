package com.example.common.auth.model;

/**
 * 认证用户的持久化模型，对应业务库中的用户表记录。
 *
 * <p>{@code common} 只定义结构，实际读写由业务模块通过 {@code AuthUserRepository} 适配，
 * 再由 {@code AuthServiceImpl} 在注册、登录时使用。</p>
 *
 * <p>本对象携带 BCrypt 摘要 {@code passwordHash}，只允许在服务端校验流程内流转，
 * 禁止直接作为接口返回值；对外统一使用不含摘要的 {@code AuthUserPrincipal}。</p>
 */
public class AuthUser {

    private Long id;

    private String username;

    private String displayName;

    /** 密码的 BCrypt 摘要，不是明文；日志与响应都不得输出该字段。 */
    private String passwordHash;

    private String role;

    /** 账号是否可用；为 {@code false} 时登录一律失败，但记录仍然保留。 */
    private boolean enabled;

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getUsername() {
        return username;
    }

    public void setUsername(String username) {
        this.username = username;
    }

    public String getDisplayName() {
        return displayName;
    }

    public void setDisplayName(String displayName) {
        this.displayName = displayName;
    }

    public String getPasswordHash() {
        return passwordHash;
    }

    public void setPasswordHash(String passwordHash) {
        this.passwordHash = passwordHash;
    }

    public String getRole() {
        return role;
    }

    public void setRole(String role) {
        this.role = role;
    }

    public boolean isEnabled() {
        return enabled;
    }

    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
    }
}
