package com.example.website.integration.local;

public class LocalServiceException extends RuntimeException {
    private final int status;

    public LocalServiceException(int status, String message) {
        super(message);
        this.status = status;
    }

    public int getStatus() {
        return status;
    }
}
