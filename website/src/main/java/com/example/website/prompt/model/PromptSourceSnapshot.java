package com.example.website.prompt.model;

import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public class PromptSourceSnapshot {

    private String sourceId;
    private String name;
    private String url;
    private String type;
    private List<String> tags = new ArrayList<String>();
    private String status;
    private String summary;
    private OffsetDateTime lastFetchedAt;
    private String message;

    public PromptSourceSnapshot() {
    }

    public PromptSourceSnapshot(String sourceId,
                                String name,
                                String url,
                                String type,
                                List<String> tags,
                                String status,
                                String summary,
                                OffsetDateTime lastFetchedAt,
                                String message) {
        this.sourceId = sourceId;
        this.name = name;
        this.url = url;
        this.type = type;
        this.tags = tags == null ? new ArrayList<String>() : new ArrayList<String>(tags);
        this.status = status;
        this.summary = summary;
        this.lastFetchedAt = lastFetchedAt;
        this.message = message;
    }

    public String getSourceId() {
        return sourceId;
    }

    public void setSourceId(String sourceId) {
        this.sourceId = sourceId;
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

    public String getType() {
        return type;
    }

    public void setType(String type) {
        this.type = type;
    }

    public List<String> getTags() {
        return Collections.unmodifiableList(tags);
    }

    public void setTags(List<String> tags) {
        this.tags = tags == null ? new ArrayList<String>() : new ArrayList<String>(tags);
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public String getSummary() {
        return summary;
    }

    public void setSummary(String summary) {
        this.summary = summary;
    }

    public OffsetDateTime getLastFetchedAt() {
        return lastFetchedAt;
    }

    public void setLastFetchedAt(OffsetDateTime lastFetchedAt) {
        this.lastFetchedAt = lastFetchedAt;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }
}
