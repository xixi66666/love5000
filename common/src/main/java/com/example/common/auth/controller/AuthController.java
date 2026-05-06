package com.example.common.auth.controller;

import com.example.common.auth.dto.AuthRequest;
import com.example.common.auth.model.AuthUserPrincipal;
import com.example.common.auth.service.AuthService;
import org.springframework.boot.autoconfigure.condition.ConditionalOnBean;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/auth")
@ConditionalOnBean(AuthService.class)
public class AuthController {

    private final AuthService authService;

    public AuthController(AuthService authService) {
        this.authService = authService;
    }

    @PostMapping("/register")
    public Map<String, Object> register(@RequestBody AuthRequest authRequest, HttpServletRequest request) {
        AuthUserPrincipal user = authService.register(authRequest, request);
        return userResponse("Register succeeded", user);
    }

    @PostMapping("/login")
    public Map<String, Object> login(@RequestBody AuthRequest authRequest, HttpServletRequest request) {
        AuthUserPrincipal user = authService.login(authRequest, request);
        return userResponse("Login succeeded", user);
    }

    @PostMapping("/logout")
    public Map<String, Object> logout(HttpServletRequest request, HttpServletResponse response) {
        authService.logout(request, response);
        Map<String, Object> result = new HashMap<String, Object>();
        result.put("success", true);
        result.put("message", "Logout succeeded");
        return result;
    }

    @GetMapping("/me")
    public Map<String, Object> me(HttpServletRequest request) {
        Map<String, Object> result = new HashMap<String, Object>();
        result.put("success", true);
        result.put("user", authService.currentUser(request).orElse(null));
        return result;
    }

    private Map<String, Object> userResponse(String message, AuthUserPrincipal user) {
        Map<String, Object> result = new HashMap<String, Object>();
        result.put("success", true);
        result.put("message", message);
        result.put("user", user);
        return result;
    }
}
