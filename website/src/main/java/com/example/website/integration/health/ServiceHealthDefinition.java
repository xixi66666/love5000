package com.example.website.integration.health;

public class ServiceHealthDefinition {

    private String name;
    private String url;

    public ServiceHealthDefinition() {
    }

    public ServiceHealthDefinition(String name, String url) {
        this.name = name;
        this.url = url;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getUrl() {
        return url;
    }

    public void setUrl(String url) {
        this.url = url;
    }
}
