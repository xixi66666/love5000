package com.example.common.auth.model;

import java.io.Serializable;

/**
 * 写入 Session 的登录主体快照。
 *
 * <p>会话默认按 Java 序列化保存，所以必须实现 {@link Serializable}；
 * 刻意不包含 {@code passwordHash}，即使会话数据外泄也不会暴露凭据。</p>
 *
 * <p>唯一的构造入口是 {@link #from(AuthUser)}，用于把持久化模型裁剪成最小登录信息。</p>
 */
public class AuthUserPrincipal implements Serializable {

    private Long id;

    private String username;

    private String displayName;

    private String role;

    /**
     * 由持久化模型生成会话主体，丢弃密码摘要与启用状态。
     *
     * @param authUser 已通过校验的用户记录，不得为 {@code null}
     * @return 只含标识、用户名、展示名与角色的新主体
     */
    public static AuthUserPrincipal from(AuthUser authUser) {
        AuthUserPrincipal principal = new AuthUserPrincipal();
        principal.setId(authUser.getId());
        principal.setUsername(authUser.getUsername());
        principal.setDisplayName(authUser.getDisplayName());
        principal.setRole(authUser.getRole());
        return principal;
    }

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

    public String getRole() {
        return role;
    }

    public void setRole(String role) {
        this.role = role;
    }
}
