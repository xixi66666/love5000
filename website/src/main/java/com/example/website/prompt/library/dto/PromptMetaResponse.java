package com.example.website.prompt.library.dto;

import java.util.List;

/**
 * {@code GET /api/prompts/meta} 的响应体，用于渲染提示词库的筛选面板。
 *
 * <p>由三条聚合统计拼装而成：{@code groups} 是大分类树（每个大分类挂自己的小分类与计数），
 * {@code sources} 是来源列表（含授权与摘要），{@code total} 是全库条目数。
 * 所有集合都保证非 {@code null}，没有数据的分类会返回空的小分类列表而不是缺字段。</p>
 */
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

    /**
     * 一级分类（大分类）汇总，按 {@code prompt_group.sort_order} 排序。
     *
     * <p>{@code slug} 是前端传回 {@code GET /api/prompts?group=} 的值；{@code count} 是该大分类下
     * 的条目数，可能为 0（分类已建但还没有提示词）；{@code categories} 为二级分类，绝不返回 {@code null}。</p>
     */
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

    /**
     * 二级分类（小分类）汇总。
     *
     * <p>{@code name} 是数据库里的小分类原文，前端原样作为 {@code GET /api/prompts?category=} 的入参，
     * 服务端按等值匹配，不做大小写或同义词归一化。</p>
     */
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

    /**
     * 来源汇总。
     *
     * <p>{@code id} 用于 {@code GET /api/prompts?source=} 过滤；{@code status} 是来源自身的状态标识
     * （例如 {@code imported}），与单条提示词的 {@code status} 不是同一概念；
     * {@code license}/{@code summary} 可能为空串，前端需容忍空值。</p>
     */
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