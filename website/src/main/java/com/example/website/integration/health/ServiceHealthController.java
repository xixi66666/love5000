package com.example.website.integration.health;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/services")
public class ServiceHealthController {

    private final ServiceHealthMonitor monitor;

    public ServiceHealthController(ServiceHealthMonitor monitor) {
        this.monitor = monitor;
    }

    @GetMapping("/health")
    public ServiceHealthSummary health() {
        return monitor.snapshot();
    }
}
