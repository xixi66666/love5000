package com.example.common.auth.exception;

import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

import java.util.Collections;
import java.util.List;

public class AuthException extends ResponseStatusException {

    private final String code;

    private final List<String> details;

    public AuthException(HttpStatus status, String reason) {
        this(status, reason, "AUTH_ERROR", Collections.emptyList());
    }

    public AuthException(HttpStatus status, String reason, String code, List<String> details) {
        super(status, reason);
        this.code = code;
        this.details = details == null ? Collections.emptyList() : details;
    }

    public String getCode() {
        return code;
    }

    public List<String> getDetails() {
        return details;
    }
}
