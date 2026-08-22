package com.example.website.integration.health;

import java.util.List;

public class ServiceHealthSummary {

    private final boolean success;
    private final boolean healthy;
    private final List<ServiceHealthResult> services;

    public ServiceHealthSummary(boolean success,
                                boolean healthy,
                                List<ServiceHealthResult> services) {
        this.success = success;
        this.healthy = healthy;
        this.services = services;
    }

    public boolean isSuccess() {
        return success;
    }

    public boolean isHealthy() {
        return healthy;
    }

    public List<ServiceHealthResult> getServices() {
        return services;
    }
}
