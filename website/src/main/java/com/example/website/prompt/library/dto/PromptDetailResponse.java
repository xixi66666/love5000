package com.example.website.prompt.library.dto;

import java.util.List;

public class PromptDetailResponse {

    private boolean success = true;
    private EntryDetail entry;

    public boolean isSuccess() {
        return success;
    }

    public void setSuccess(boolean success) {
        this.success = success;
    }

    public EntryDetail getEntry() {
        return entry;
    }

    public void setEntry(EntryDetail entry) {
        this.entry = entry;
    }

    public static class EntryDetail {

        private Long id;
        private String title;
        private String category;
        private String groupSlug;
        private String groupName;
        private String sourceName;
        private String sourceUrl;
        private List<String> tags;
        private String license;
        private String status;
        private String prompt;

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

        public String getCategory() {
            return category;
        }

        public void setCategory(String category) {
            this.category = category;
        }

        public String getGroupSlug() {
            return groupSlug;
        }

        public void setGroupSlug(String groupSlug) {
            this.groupSlug = groupSlug;
        }

        public String getGroupName() {
            return groupName;
        }

        public void setGroupName(String groupName) {
            this.groupName = groupName;
        }

        public String getSourceName() {
            return sourceName;
        }

        public void setSourceName(String sourceName) {
            this.sourceName = sourceName;
        }

        public String getSourceUrl() {
            return sourceUrl;
        }

        public void setSourceUrl(String sourceUrl) {
            this.sourceUrl = sourceUrl;
        }

        public List<String> getTags() {
            return tags;
        }

        public void setTags(List<String> tags) {
            this.tags = tags;
        }

        public String getLicense() {
            return license;
        }

        public void setLicense(String license) {
            this.license = license;
        }

        public String getStatus() {
            return status;
        }

        public void setStatus(String status) {
            this.status = status;
        }

        public String getPrompt() {
            return prompt;
        }

        public void setPrompt(String prompt) {
            this.prompt = prompt;
        }
    }
}