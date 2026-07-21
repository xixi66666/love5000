package com.example.guitar.auth.model;

import com.example.guitar.user.model.GuitarUser;

import java.io.Serializable;

public class GuitarUserPrincipal implements Serializable {

    private static final long serialVersionUID = 1L;

    private final Long id;
    private final String phone;
    private final String nickname;
    private final String avatarObjectKey;
    private final String role;

    public GuitarUserPrincipal(Long id, String phone, String nickname,
                               String avatarObjectKey, String role) {
        this.id = id;
        this.phone = phone;
        this.nickname = nickname;
        this.avatarObjectKey = avatarObjectKey;
        this.role = role;
    }

    public static GuitarUserPrincipal from(GuitarUser user) {
        return new GuitarUserPrincipal(user.getId(), user.getPhone(), user.getNickname(),
                user.getAvatarObjectKey(), user.getRole());
    }

    public Long getId() {
        return id;
    }

    public String getPhone() {
        return phone;
    }

    public String getNickname() {
        return nickname;
    }

    public String getAvatarObjectKey() {
        return avatarObjectKey;
    }

    public String getRole() {
        return role;
    }
}
