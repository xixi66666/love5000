package com.example.common.auth.repository;

import com.example.common.auth.model.AuthUser;

import java.util.Optional;

public interface AuthUserRepository {

    Optional<AuthUser> findByUsername(String username);

    Optional<AuthUser> findById(Long id);

    Long save(String username, String passwordHash, String displayName, String role);
}
