package com.example.common.auth.service;

import com.example.common.auth.dto.AuthLoginRequest;
import com.example.common.auth.dto.AuthRegisterRequest;
import com.example.common.auth.model.AuthUserPrincipal;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.util.Optional;

public interface AuthService {

    AuthUserPrincipal register(AuthRegisterRequest authRequest, HttpServletRequest request);

    AuthUserPrincipal login(AuthLoginRequest authRequest, HttpServletRequest request);

    void logout(HttpServletRequest request, HttpServletResponse response);

    Optional<AuthUserPrincipal> currentUser(HttpServletRequest request);

    AuthUserPrincipal requireCurrentUser(HttpServletRequest request);
}
