package com.example.website.integration.health;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/services")
public class ServiceHealthController {

    private final ServiceHealthAggregator aggregator;

    public ServiceHealthController(ServiceHealthAggregator aggregator) {
        this.aggregator = aggregator;
    }

    @GetMapping("/health")
    public ServiceHealthSummary health() {
        return aggregator.checkAll();
    }
}
