package com.example.guitar.web;

import org.springframework.http.HttpStatus;

public class GuitarApiException extends RuntimeException {

    private final HttpStatus status;
    private final String code;

    public GuitarApiException(HttpStatus status, String code, String message) {
        super(message);
        this.status = status;
        this.code = code;
    }

    public HttpStatus getStatus() {
        return status;
    }

    public String getCode() {
        return code;
    }
}
