package com.example.imagetemplate.model;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class ImagePromptTemplate {

    private String id;

    private String title;

    private String category;

    private String categorySlug;

    private String summary;

    private List<String> tags = new ArrayList<String>();

    private Map<String, Object> jsonTemplate = new LinkedHashMap<String, Object>();

    private String promptTemplate;

    private String sourceUrl;

    private String sourceId;

    private String sourceName;

    private String functionCategory;

    private String functionCategorySlug;

    private String functionScene;

    private String functionSceneSlug;

    private String templateKind;

    private boolean imageRelated;

    private boolean curated;

    public String getId() {
        return id;
    }

    public void setId(String id) {
        this.id = id;
    }

    public String getTitle() {
        return title;
    }

    public void setTitle(String title) {
        this.title = title;
    }

    public String getCategory() {
        return category;
    }

    public void setCategory(String category) {
        this.category = category;
    }

    public String getCategorySlug() {
        return categorySlug;
    }

    public void setCategorySlug(String categorySlug) {
        this.categorySlug = categorySlug;
    }

    public String getSummary() {
        return summary;
    }

    public void setSummary(String summary) {
        this.summary = summary;
    }

    public List<String> getTags() {
        return tags;
    }

    public void setTags(List<String> tags) {
        this.tags = tags;
    }

    public Map<String, Object> getJsonTemplate() {
        return jsonTemplate;
    }

    public void setJsonTemplate(Map<String, Object> jsonTemplate) {
        this.jsonTemplate = jsonTemplate;
    }

    public String getPromptTemplate() {
        return promptTemplate;
    }

    public void setPromptTemplate(String promptTemplate) {
        this.promptTemplate = promptTemplate;
    }

    public String getSourceUrl() {
        return sourceUrl;
    }

    public void setSourceUrl(String sourceUrl) {
        this.sourceUrl = sourceUrl;
    }

    public String getSourceId() {
        return sourceId;
    }

    public void setSourceId(String sourceId) {
        this.sourceId = sourceId;
    }

    public String getSourceName() {
        return sourceName;
    }

    public void setSourceName(String sourceName) {
        this.sourceName = sourceName;
    }

    public String getFunctionCategory() {
        return functionCategory;
    }

    public void setFunctionCategory(String functionCategory) {
        this.functionCategory = functionCategory;
    }

    public String getFunctionCategorySlug() {
        return functionCategorySlug;
    }

    public void setFunctionCategorySlug(String functionCategorySlug) {
        this.functionCategorySlug = functionCategorySlug;
    }

    public String getFunctionScene() {
        return functionScene;
    }

    public void setFunctionScene(String functionScene) {
        this.functionScene = functionScene;
    }

    public String getFunctionSceneSlug() {
        return functionSceneSlug;
    }

    public void setFunctionSceneSlug(String functionSceneSlug) {
        this.functionSceneSlug = functionSceneSlug;
    }

    public String getTemplateKind() {
        return templateKind;
    }

    public void setTemplateKind(String templateKind) {
        this.templateKind = templateKind;
    }

    public boolean isImageRelated() {
        return imageRelated;
    }

    public void setImageRelated(boolean imageRelated) {
        this.imageRelated = imageRelated;
    }

    public boolean isCurated() {
        return curated;
    }

    public void setCurated(boolean curated) {
        this.curated = curated;
    }
}
