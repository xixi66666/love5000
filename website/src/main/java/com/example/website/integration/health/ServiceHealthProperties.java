package com.example.website.integration.health;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

import javax.annotation.PostConstruct;
import java.net.URI;
import java.net.URISyntaxException;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

@Component
@ConfigurationProperties(prefix = "website.service-health")
public class ServiceHealthProperties {

    private int connectTimeoutMs = 2000;
    private int readTimeoutMs = 3000;
    private List<ServiceHealthDefinition> services = new ArrayList<>();

    @PostConstruct
    public void validate() {
        if (connectTimeoutMs <= 0) {
            throw new IllegalStateException("website.service-health.connect-timeout-ms must be positive");
        }
        if (readTimeoutMs <= 0) {
            throw new IllegalStateException("website.service-health.read-timeout-ms must be positive");
        }

        Set<String> names = new HashSet<>();
        for (int i = 0; i < services.size(); i++) {
            ServiceHealthDefinition definition = services.get(i);
            if (definition == null || isBlank(definition.getName())) {
                throw new IllegalStateException("website.service-health service[" + i + "] name must not be blank");
            }
            String name = definition.getName().trim();
            definition.setName(name);
            if (!names.add(name)) {
                throw new IllegalStateException("duplicate service name: " + name);
            }
            validateUrl(name, definition.getUrl());
        }
    }

    private void validateUrl(String name, String url) {
        if (isBlank(url)) {
            throw new IllegalStateException("service " + name + " has an invalid health URL");
        }
        try {
            String scheme = new URI(url).getScheme();
            String normalizedScheme = scheme == null ? "" : scheme.toLowerCase(Locale.ROOT);
            if (!"http".equals(normalizedScheme) && !"https".equals(normalizedScheme)) {
                throw new IllegalStateException("service " + name + " has an invalid health URL scheme");
            }
        } catch (URISyntaxException e) {
            throw new IllegalStateException("service " + name + " has an invalid health URL");
        }
    }

    private boolean isBlank(String value) {
        return value == null || value.trim().isEmpty();
    }

    public int getConnectTimeoutMs() {
        return connectTimeoutMs;
    }

    public void setConnectTimeoutMs(int connectTimeoutMs) {
        this.connectTimeoutMs = connectTimeoutMs;
    }

    public int getReadTimeoutMs() {
        return readTimeoutMs;
    }

    public void setReadTimeoutMs(int readTimeoutMs) {
        this.readTimeoutMs = readTimeoutMs;
    }

    public List<ServiceHealthDefinition> getServices() {
        return services;
    }

    public void setServices(List<ServiceHealthDefinition> services) {
        this.services = services == null ? new ArrayList<>() : services;
    }
}
