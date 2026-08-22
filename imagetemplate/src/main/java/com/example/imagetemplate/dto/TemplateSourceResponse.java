package com.example.imagetemplate.dto;

public class TemplateSourceResponse {

    private String id;

    private String name;

    private String url;

    private int count;

    public TemplateSourceResponse() {
    }

    public TemplateSourceResponse(String id, String name, String url, int count) {
        this.id = id;
        this.name = name;
        this.url = url;
        this.count = count;
    }

    public String getId() {
        return id;
    }

    public String getName() {
        return name;
    }

    public String getUrl() {
        return url;
    }

    public int getCount() {
        return count;
    }
}
