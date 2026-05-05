package com.example.common.auth.model;

import java.io.Serializable;

public class AuthUserPrincipal implements Serializable {

    private Long id;

    private String username;

    private String displayName;

    private String role;

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
