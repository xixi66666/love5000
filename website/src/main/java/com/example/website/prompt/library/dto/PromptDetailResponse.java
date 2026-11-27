package com.example.website.prompt.library.dto;

import java.util.List;

/**
 * {@code GET /api/prompts/{id}} 的响应体。
 *
 * <p>{@code success} 默认 {@code true}；条目不存在时控制器返回的是
 * {@code {"success":false,"message":"提示词不存在"}} 的 404 响应，不会生成本对象，
 * 因此这里只描述命中时的形态。</p>
 */
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

    /**
     * 单条提示词的完整详情。
     *
     * <p>与列表摘要的区别：这里返回不截断的 {@code prompt} 和 {@code sourceUrl}；
     * {@code tags} 已在服务层从数据库的逗号分隔串拆成列表；{@code groupName}/{@code sourceName}
     * 来自 {@code prompt_group}/{@code prompt_source} 的左连接，来源或分类被删除时为 {@code null}。</p>
     */
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