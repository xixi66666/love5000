package com.example.common.auth.controller;

import com.example.common.auth.exception.AuthException;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.HashMap;
import java.util.Map;

@RestControllerAdvice
public class AuthExceptionHandler {

    @ExceptionHandler(AuthException.class)
    public ResponseEntity<Map<String, Object>> handleAuthException(AuthException exception) {
        Map<String, Object> response = new HashMap<String, Object>();
        response.put("success", false);
        response.put("code", exception.getCode());
        response.put("message", exception.getReason());
        response.put("details", exception.getDetails());
        return ResponseEntity.status(exception.getStatus()).body(response);
    }
}
