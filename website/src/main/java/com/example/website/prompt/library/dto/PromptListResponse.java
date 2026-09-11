package com.example.website.prompt.library.dto;

import java.util.List;

public class PromptListResponse {

    private boolean success = true;
    private long total;
    private int page;
    private int size;
    private List<EntrySummary> entries;

    public boolean isSuccess() {
        return success;
    }

    public void setSuccess(boolean success) {
        this.success = success;
    }

    public long getTotal() {
        return total;
    }

    public void setTotal(long total) {
        this.total = total;
    }

    public int getPage() {
        return page;
    }

    public void setPage(int page) {
        this.page = page;
    }

    public int getSize() {
        return size;
    }

    public void setSize(int size) {
        this.size = size;
    }

    public List<EntrySummary> getEntries() {
        return entries;
    }

    public void setEntries(List<EntrySummary> entries) {
        this.entries = entries;
    }

    public static class EntrySummary {

        private Long id;
        private String title;
        private String category;
        private String groupSlug;
        private String groupName;
        private String sourceName;
        private List<String> tags;
        private String license;
        private String status;
        private String preview;

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

        public String getPreview() {
            return preview;
        }

        public void setPreview(String preview) {
            this.preview = preview;
        }
    }
}