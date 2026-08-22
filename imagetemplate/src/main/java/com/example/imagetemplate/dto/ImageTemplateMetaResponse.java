package com.example.imagetemplate.dto;

import com.example.imagetemplate.model.LibraryAggregationStatus;

import java.util.ArrayList;
import java.util.List;

public class ImageTemplateMetaResponse {

    private boolean success = true;

    private int total;

    private int curatedCount;

    private int libraryCount;

    private int imageRelatedCount;

    private LibraryAggregationStatus status;

    private List<TemplateSourceResponse> sources = new ArrayList<TemplateSourceResponse>();

    private List<TemplateCategoryResponse> categories =
            new ArrayList<TemplateCategoryResponse>();

    private List<TemplateFunctionCategoryResponse> functionCategories =
            new ArrayList<TemplateFunctionCategoryResponse>();

    public boolean isSuccess() {
        return success;
    }

    public int getTotal() {
        return total;
    }

    public void setTotal(int total) {
        this.total = total;
    }

    public int getCuratedCount() {
        return curatedCount;
    }

    public void setCuratedCount(int curatedCount) {
        this.curatedCount = curatedCount;
    }

    public int getLibraryCount() {
        return libraryCount;
    }

    public void setLibraryCount(int libraryCount) {
        this.libraryCount = libraryCount;
    }

    public int getImageRelatedCount() {
        return imageRelatedCount;
    }

    public void setImageRelatedCount(int imageRelatedCount) {
        this.imageRelatedCount = imageRelatedCount;
    }

    public LibraryAggregationStatus getStatus() {
        return status;
    }

    public void setStatus(LibraryAggregationStatus status) {
        this.status = status;
    }

    public List<TemplateSourceResponse> getSources() {
        return sources;
    }

    public void setSources(List<TemplateSourceResponse> sources) {
        this.sources = sources;
    }

    public List<TemplateCategoryResponse> getCategories() {
        return categories;
    }

    public void setCategories(List<TemplateCategoryResponse> categories) {
        this.categories = categories;
    }

    public List<TemplateFunctionCategoryResponse> getFunctionCategories() {
        return functionCategories;
    }

    public void setFunctionCategories(
            List<TemplateFunctionCategoryResponse> functionCategories) {
        this.functionCategories = functionCategories;
    }
}
