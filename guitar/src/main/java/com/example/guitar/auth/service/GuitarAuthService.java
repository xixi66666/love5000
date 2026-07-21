package com.example.guitar.auth.service;

import com.example.guitar.auth.dto.LoginRequest;
import com.example.guitar.auth.dto.RegisterRequest;
import com.example.guitar.auth.model.GuitarUserPrincipal;

import javax.servlet.http.HttpServletRequest;
import java.util.Optional;

public interface GuitarAuthService {

    String SESSION_ATTRIBUTE = "GUITAR_AUTH_USER";

    GuitarUserPrincipal register(RegisterRequest registerRequest, HttpServletRequest request);

    GuitarUserPrincipal login(LoginRequest loginRequest, HttpServletRequest request);

    void logout(HttpServletRequest request);

    Optional<GuitarUserPrincipal> currentSession(HttpServletRequest request);
}
