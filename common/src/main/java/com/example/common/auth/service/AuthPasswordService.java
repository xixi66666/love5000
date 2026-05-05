package com.example.common.auth.service;

import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;

public class AuthPasswordService {

    private final BCryptPasswordEncoder passwordEncoder = new BCryptPasswordEncoder();

    public String hash(String rawPassword) {
        return passwordEncoder.encode(rawPassword);
    }

    public boolean matches(String rawPassword, String passwordHash) {
        return passwordEncoder.matches(rawPassword, passwordHash);
    }
}
