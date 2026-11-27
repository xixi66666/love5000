package com.example.common.auth.controller;

import com.example.common.auth.exception.AuthException;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.HashMap;
import java.util.Map;

/**
 * 认证异常的全局响应转换器。
 *
 * <p>只处理 {@code AuthException}：用异常携带的 HTTP 状态作为响应状态，
 * 并把 {@code code} 与逐条 {@code details} 放进响应体，形成
 * {@code {success:false, code, message, details}} 的统一失败结构。</p>
 *
 * <p>刻意不拦截其他异常，避免把 404、参数解析失败等既有语义也改写成本结构；
 * 由于这里注册了更具体的处理器，{@code ResponseStatusException} 的默认处理不会再生效。</p>
 */
@RestControllerAdvice
public class AuthExceptionHandler {

    /**
     * 将认证异常映射为响应实体。
     *
     * @param exception 认证流程抛出的异常，状态码与原因均取自异常本身
     * @return 状态码与异常一致、响应体为统一失败结构的实体
     */
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
