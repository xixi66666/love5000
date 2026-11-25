package com.example.imagetemplate.service;

import com.example.imagetemplate.model.ImagePromptTemplate;

import java.util.Locale;

/**
 * Precomputed, immutable search fields for a single template. Built once at
 * aggregation time so that list-page matching never re-normalizes or re-joins
 * the same strings on every request.
 */
final class TemplateSearchIndex {

    private final String normalizedKeywordHaystack;

    private final String normalizedSourceId;

    private final String normalizedCategorySlug;

    private final String normalizedCategoryName;

    private final String normalizedFunctionCategorySlug;

    private final String normalizedFunctionCategoryName;

    private final String normalizedFunctionSceneSlug;

    private final String normalizedFunctionSceneName;

    TemplateSearchIndex(ImagePromptTemplate template) {
        this.normalizedKeywordHaystack = normalize(buildKeywordHaystack(template));
        this.normalizedSourceId = normalize(template.getSourceId());
        this.normalizedCategorySlug = normalize(template.getCategorySlug());
        this.normalizedCategoryName = normalize(template.getCategory());
        this.normalizedFunctionCategorySlug = normalize(template.getFunctionCategorySlug());
        this.normalizedFunctionCategoryName = normalize(template.getFunctionCategory());
        this.normalizedFunctionSceneSlug = normalize(template.getFunctionSceneSlug());
        this.normalizedFunctionSceneName = normalize(template.getFunctionScene());
    }

    boolean matchesKeyword(String normalizedKeyword) {
        return normalizedKeywordHaystack.contains(normalizedKeyword);
    }

    boolean matchesSource(String normalizedSource) {
        return normalizedSourceId.equals(normalizedSource);
    }

    boolean matchesCategory(String normalizedCategory) {
        return normalizedCategorySlug.equals(normalizedCategory)
                || normalizedCategoryName.equals(normalizedCategory);
    }

    boolean matchesFunctionCategory(String normalizedCategory) {
        return normalizedFunctionCategorySlug.equals(normalizedCategory)
                || normalizedFunctionCategoryName.equals(normalizedCategory);
    }

    boolean matchesFunctionScene(String normalizedScene) {
        return normalizedFunctionSceneSlug.equals(normalizedScene)
                || normalizedFunctionSceneName.equals(normalizedScene);
    }

    private static String buildKeywordHaystack(ImagePromptTemplate template) {
        StringBuilder haystack = new StringBuilder();
        haystack.append(template.getTitle()).append(' ')
                .append(template.getSummary()).append(' ')
                .append(template.getCategory()).append(' ')
                .append(template.getSourceName()).append(' ')
                .append(template.getPromptTemplate());
        if (template.getTags() != null) {
            for (String tag : template.getTags()) {
                haystack.append(' ').append(tag);
            }
        }
        return haystack.toString();
    }

    private static String normalize(String value) {
        return value == null ? "" : value.trim().toLowerCase(Locale.ROOT);
    }
}
