package com.example.website.integration.personalagent;

public class PersonalAgentStartResult {

    public static final String STATUS_STARTED = "started";
    public static final String STATUS_ALREADY_RUNNING = "already-running";

    private final String status;
    private final String url;

    public PersonalAgentStartResult(String status, String url) {
        this.status = status;
        this.url = url;
    }

    public String getStatus() {
        return status;
    }

    public String getUrl() {
        return url;
    }
}
