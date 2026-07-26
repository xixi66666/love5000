package com.example.imagetemplate.model;

public final class TemplateFunctionClassification {

    private final String categoryName;

    private final String categorySlug;

    private final String sceneName;

    private final String sceneSlug;

    public TemplateFunctionClassification(String categoryName,
                                          String categorySlug,
                                          String sceneName,
                                          String sceneSlug) {
        this.categoryName = categoryName;
        this.categorySlug = categorySlug;
        this.sceneName = sceneName;
        this.sceneSlug = sceneSlug;
    }

    public String getCategoryName() {
        return categoryName;
    }

    public String getCategorySlug() {
        return categorySlug;
    }

    public String getSceneName() {
        return sceneName;
    }

    public String getSceneSlug() {
        return sceneSlug;
    }
}
