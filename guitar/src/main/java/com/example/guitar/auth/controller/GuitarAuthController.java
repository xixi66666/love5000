package com.example.guitar.auth.controller;

import com.example.guitar.auth.dto.LoginRequest;
import com.example.guitar.auth.dto.RegisterRequest;
import com.example.guitar.auth.model.GuitarUserPrincipal;
import com.example.guitar.auth.service.GuitarAuthService;
import com.example.guitar.auth.web.CsrfTokenService;
import com.example.guitar.web.ApiResponse;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.servlet.http.HttpServletRequest;
import java.util.LinkedHashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/auth")
public class GuitarAuthController {

    private final GuitarAuthService authService;
    private final CsrfTokenService csrfTokenService;

    public GuitarAuthController(GuitarAuthService authService, CsrfTokenService csrfTokenService) {
        this.authService = authService;
        this.csrfTokenService = csrfTokenService;
    }

    @PostMapping("/register")
    public ApiResponse<GuitarUserPrincipal> register(@RequestBody RegisterRequest registerRequest,
                                                     HttpServletRequest request) {
        return ApiResponse.success(authService.register(registerRequest, request));
    }

    @PostMapping("/login")
    public ApiResponse<GuitarUserPrincipal> login(@RequestBody LoginRequest loginRequest,
                                                  HttpServletRequest request) {
        return ApiResponse.success(authService.login(loginRequest, request));
    }

    @PostMapping("/logout")
    public ApiResponse<Void> logout(HttpServletRequest request) {
        authService.logout(request);
        return ApiResponse.success(null);
    }

    @GetMapping("/session")
    public ApiResponse<Map<String, Object>> session(HttpServletRequest request) {
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("user", authService.currentSession(request).orElse(null));
        data.put("csrfToken", csrfTokenService.getOrCreateToken(request.getSession(true)));
        return ApiResponse.success(data);
    }
}
