package com.example.imagetemplate.dto;

import java.util.ArrayList;
import java.util.List;

public class TemplateFunctionCategoryResponse {

    private String name;

    private String slug;

    private int count;

    private List<TemplateFunctionSceneResponse> scenes =
            new ArrayList<TemplateFunctionSceneResponse>();

    public TemplateFunctionCategoryResponse() {
    }

    public TemplateFunctionCategoryResponse(String name,
                                            String slug,
                                            int count,
                                            List<TemplateFunctionSceneResponse> scenes) {
        this.name = name;
        this.slug = slug;
        this.count = count;
        this.scenes = scenes;
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

    public List<TemplateFunctionSceneResponse> getScenes() {
        return scenes;
    }

    public void setScenes(List<TemplateFunctionSceneResponse> scenes) {
        this.scenes = scenes;
    }
}
