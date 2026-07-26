package com.example.imagetemplate.dto;

import com.example.imagetemplate.model.ImagePromptTemplate;

import java.util.ArrayList;
import java.util.List;

public class ImageTemplateSummaryResponse {

    private String id;

    private String title;

    private String summary;

    private String category;

    private String categorySlug;

    private List<String> tags = new ArrayList<String>();

    private String sourceId;

    private String sourceName;

    private String functionCategory;

    private String functionCategorySlug;

    private String functionScene;

    private String functionSceneSlug;

    private String templateKind;

    private boolean imageRelated;

    private boolean curated;

    public static ImageTemplateSummaryResponse from(ImagePromptTemplate template) {
        ImageTemplateSummaryResponse response = new ImageTemplateSummaryResponse();
        response.id = template.getId();
        response.title = template.getTitle();
        response.summary = template.getSummary();
        response.category = template.getCategory();
        response.categorySlug = template.getCategorySlug();
        response.tags = template.getTags() == null
                ? new ArrayList<String>()
                : new ArrayList<String>(template.getTags());
        response.sourceId = template.getSourceId();
        response.sourceName = template.getSourceName();
        response.functionCategory = template.getFunctionCategory();
        response.functionCategorySlug = template.getFunctionCategorySlug();
        response.functionScene = template.getFunctionScene();
        response.functionSceneSlug = template.getFunctionSceneSlug();
        response.templateKind = template.getTemplateKind();
        response.imageRelated = template.isImageRelated();
        response.curated = template.isCurated();
        return response;
    }

    public String getId() {
        return id;
    }

    public String getTitle() {
        return title;
    }

    public String getSummary() {
        return summary;
    }

    public String getCategory() {
        return category;
    }

    public String getCategorySlug() {
        return categorySlug;
    }

    public List<String> getTags() {
        return tags;
    }

    public String getSourceId() {
        return sourceId;
    }

    public String getSourceName() {
        return sourceName;
    }

    public String getFunctionCategory() {
        return functionCategory;
    }

    public String getFunctionCategorySlug() {
        return functionCategorySlug;
    }

    public String getFunctionScene() {
        return functionScene;
    }

    public String getFunctionSceneSlug() {
        return functionSceneSlug;
    }

    public String getTemplateKind() {
        return templateKind;
    }

    public boolean isImageRelated() {
        return imageRelated;
    }

    public boolean isCurated() {
        return curated;
    }
}
