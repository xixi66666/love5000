package com.example.website.integration.health;

public class ServiceHealthResult {

    private final String name;
    private final String url;
    private final boolean healthy;
    private final Integer statusCode;
    private final long durationMs;
    private final String message;

    private ServiceHealthResult(String name,
                                String url,
                                boolean healthy,
                                Integer statusCode,
                                long durationMs,
                                String message) {
        this.name = name;
        this.url = url;
        this.healthy = healthy;
        this.statusCode = statusCode;
        this.durationMs = durationMs;
        this.message = message;
    }

    public static ServiceHealthResult healthy(ServiceHealthDefinition definition,
                                              int statusCode,
                                              long durationMs) {
        return new ServiceHealthResult(
                definition.getName(), definition.getUrl(), true, statusCode, durationMs, null);
    }

    public static ServiceHealthResult unhealthy(ServiceHealthDefinition definition,
                                                Integer statusCode,
                                                long durationMs,
                                                String message) {
        return new ServiceHealthResult(
                definition.getName(), definition.getUrl(), false, statusCode, durationMs, message);
    }

    public String getName() {
        return name;
    }

    public String getUrl() {
        return url;
    }

    public boolean isHealthy() {
        return healthy;
    }

    public Integer getStatusCode() {
        return statusCode;
    }

    public long getDurationMs() {
        return durationMs;
    }

    public String getMessage() {
        return message;
    }
}
