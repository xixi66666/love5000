package com.example.website.blog.dto;

import com.example.website.blog.model.BlogArticle;

import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public class BlogArticleResponse {

    private static final DateTimeFormatter DATE_TIME_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private Long id;

    private String title;

    private String slug;

    private String summary;

    private String contentHtml;

    private String category;

    private List<String> tags;

    private Long authorId;

    private String authorUsername;

    private String authorDisplayName;

    private Integer wordCount;

    private Integer readMinutes;

    private String publishedAt;

    public static BlogArticleResponse from(BlogArticle article, boolean includeContent) {
        BlogArticleResponse response = new BlogArticleResponse();
        response.setId(article.getId());
        response.setTitle(article.getTitle());
        response.setSlug(article.getSlug());
        response.setSummary(article.getSummary());
        response.setCategory(article.getCategory());
        response.setTags(parseTags(article.getTags()));
        response.setAuthorId(article.getAuthorId());
        response.setAuthorUsername(article.getAuthorUsername());
        response.setAuthorDisplayName(article.getAuthorDisplayName());
        response.setWordCount(article.getWordCount());
        response.setReadMinutes(article.getReadMinutes());
        response.setPublishedAt(article.getPublishedAt() == null ? null : article.getPublishedAt().format(DATE_TIME_FORMATTER));
        if (includeContent) {
            response.setContentHtml(article.getContentHtml());
        }
        return response;
    }

    private static List<String> parseTags(String tags) {
        if (tags == null || tags.trim().isEmpty()) {
            return Collections.emptyList();
        }
        String[] parts = tags.split(",");
        List<String> result = new ArrayList<String>();
        for (String part : parts) {
            String normalized = part.trim();
            if (!normalized.isEmpty()) {
                result.add(normalized);
            }
        }
        return result;
    }

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getTitle() {
        return title;
    }

    public void setTitle(String title) {
        this.title = title;
    }

    public String getSlug() {
        return slug;
    }

    public void setSlug(String slug) {
        this.slug = slug;
    }

    public String getSummary() {
        return summary;
    }

    public void setSummary(String summary) {
        this.summary = summary;
    }

    public String getContentHtml() {
        return contentHtml;
    }

    public void setContentHtml(String contentHtml) {
        this.contentHtml = contentHtml;
    }

    public String getCategory() {
        return category;
    }

    public void setCategory(String category) {
        this.category = category;
    }

    public List<String> getTags() {
        return tags;
    }

    public void setTags(List<String> tags) {
        this.tags = tags;
    }

    public Long getAuthorId() {
        return authorId;
    }

    public void setAuthorId(Long authorId) {
        this.authorId = authorId;
    }

    public String getAuthorUsername() {
        return authorUsername;
    }

    public void setAuthorUsername(String authorUsername) {
        this.authorUsername = authorUsername;
    }

    public String getAuthorDisplayName() {
        return authorDisplayName;
    }

    public void setAuthorDisplayName(String authorDisplayName) {
        this.authorDisplayName = authorDisplayName;
    }

    public Integer getWordCount() {
        return wordCount;
    }

    public void setWordCount(Integer wordCount) {
        this.wordCount = wordCount;
    }

    public Integer getReadMinutes() {
        return readMinutes;
    }

    public void setReadMinutes(Integer readMinutes) {
        this.readMinutes = readMinutes;
    }

    public String getPublishedAt() {
        return publishedAt;
    }

    public void setPublishedAt(String publishedAt) {
        this.publishedAt = publishedAt;
    }
}
