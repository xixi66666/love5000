package com.example.imagetemplate.dto;

/**
 * 原始分类计数的响应投影。
 *
 * <p>同时用于 {@code GET /api/image-templates/categories} 的 {@code categories} 数组和
 * {@code /meta} 的 {@code categories} 字段，属于旧版筛选维度；功能导航请使用
 * {@link TemplateFunctionCategoryResponse} 表示的两级树。</p>
 */
public class TemplateCategoryResponse {

    /** 分类中文名，来自模板数据文件的 {@code category}。 */
    private String name;

    /** 分类稳定标识，用于 {@code category} 查询参数；大库分类为由分类名哈希生成的 slug。 */
    private String slug;

    /** 该分类下的模板条数（精选与大库合并统计）。 */
    private int count;

    public TemplateCategoryResponse() {
    }

    public TemplateCategoryResponse(String name, String slug, int count) {
        this.name = name;
        this.slug = slug;
        this.count = count;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getSlug() {
        return slug;
    }

    public void setSlug(String slug) {
        this.slug = slug;
    }

    public int getCount() {
        return count;
    }

    public void setCount(int count) {
        this.count = count;
    }
}

