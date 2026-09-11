package com.example.website.prompt.library.dto;

import java.util.List;

public class PromptMetaResponse {

    private boolean success = true;
    private long total;
    private List<GroupSummary> groups;
    private List<SourceSummary> sources;

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

    public List<GroupSummary> getGroups() {
        return groups;
    }

    public void setGroups(List<GroupSummary> groups) {
        this.groups = groups;
    }

    public List<SourceSummary> getSources() {
        return sources;
    }

    public void setSources(List<SourceSummary> sources) {
        this.sources = sources;
    }

    public static class GroupSummary {

        private String slug;
        private String name;
        private long count;
        private List<CategorySummary> categories;

        public String getSlug() {
            return slug;
        }

        public void setSlug(String slug) {
            this.slug = slug;
        }

        public String getName() {
            return name;
        }

        public void setName(String name) {
            this.name = name;
        }

        public long getCount() {
            return count;
        }

        public void setCount(long count) {
            this.count = count;
        }

        public List<CategorySummary> getCategories() {
            return categories;
        }

        public void setCategories(List<CategorySummary> categories) {
            this.categories = categories;
        }
    }

    public static class CategorySummary {

        private String name;
        private long count;

        public CategorySummary() {
        }

        public CategorySummary(String name, long count) {
            this.name = name;
            this.count = count;
        }

        public String getName() {
            return name;
        }

        public void setName(String name) {
            this.name = name;
        }

        public long getCount() {
            return count;
        }

        public void setCount(long count) {
            this.count = count;
        }
    }

    public static class SourceSummary {

        private String id;
        private String name;
        private String status;
        private long count;
        private String license;
        private String summary;

        public String getId() {
            return id;
        }

        public void setId(String id) {
            this.id = id;
        }

        public String getName() {
            return name;
        }

        public void setName(String name) {
            this.name = name;
        }

        public String getStatus() {
            return status;
        }

        public void setStatus(String status) {
            this.status = status;
        }

        public long getCount() {
            return count;
        }

        public void setCount(long count) {
            this.count = count;
        }

        public String getLicense() {
            return license;
        }

        public void setLicense(String license) {
            this.license = license;
        }

        public String getSummary() {
            return summary;
        }

        public void setSummary(String summary) {
            this.summary = summary;
        }
    }
}