package com.example.imagetemplate.dto;

public class TemplateCategoryResponse {

    private String name;

    private String slug;

    private int count;

    public TemplateCategoryResponse() {
    }

    public TemplateCategoryResponse(String name, String slug, int count) {
        this.name = name;
        this.slug = slug;
        this.count = count;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getSlug() {
        return slug;
    }

    public void setSlug(String slug) {
        this.slug = slug;
    }

    public int getCount() {
        return count;
    }

    public void setCount(int count) {
        this.count = count;
    }
}
