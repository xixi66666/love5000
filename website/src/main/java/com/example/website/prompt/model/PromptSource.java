package com.example.website.prompt.model;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public class PromptSource {

    private String id;
    private String name;
    private String url;
    private String type;
    private List<String> tags = new ArrayList<String>();
    private String defaultSummary;

    public PromptSource() {
    }

    public PromptSource(String id, String name, String url, String type, List<String> tags, String defaultSummary) {
        this.id = id;
        this.name = name;
        this.url = url;
        this.type = type;
        this.tags = tags == null ? new ArrayList<String>() : new ArrayList<String>(tags);
        this.defaultSummary = defaultSummary;
    }

    public String getId() {
        return id;
    }

    public void setId(String id) {
        this.id = id;
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

    public String getDefaultSummary() {
        return defaultSummary;
    }

    public void setDefaultSummary(String defaultSummary) {
        this.defaultSummary = defaultSummary;
    }
}
