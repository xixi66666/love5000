package com.example.imagetemplate.dto;

/**
 * 模板列表查询条件。
 *
 * <p>由 Controller 从查询参数装配后交给
 * {@link com.example.imagetemplate.service.ImagePromptTemplateService#search(ImageTemplateQuery)}。
 * 本类只提供默认值，校验（{@code page >= 1}、{@code size} 在 1~100）在 service 内完成，
 * 非法值抛 {@code ImageTemplateQueryValidationException} 并被映射为 HTTP 400。</p>
 *
 * <p>字符串条件在使用前统一 trim 并转小写，空值或 {@code all} 表示不筛选；
 * 多个条件同时存在时取交集。</p>
 */
public class ImageTemplateQuery {

    /** 页码，从 1 开始，默认 1；小于 1 视为非法请求。 */
    private int page = 1;

    /** 每页条数，默认 48；允许 1~100，越界即拒绝，避免一次取回全库。 */
    private int size = 48;

    /** 关键词，默认 {@code null}；小写子串匹配标题、摘要、原始分类、来源名、标签与完整 prompt。 */
    private String keyword;

    /** 来源 ID，默认 {@code null}；精确匹配（如 {@code curated}），{@code all} 表示不筛选。 */
    private String source;

    /** 原始分类，默认 {@code null}；匹配 {@code categorySlug} 或中文分类名，{@code all} 表示不筛选。 */
    private String category;

    /** 一级功能，默认 {@code null}；匹配功能 slug 或中文名，对应工作台左侧导航。 */
    private String functionCategory;

    /** 二级场景，默认 {@code null}；匹配场景 slug 或中文名，通常与 {@code functionCategory} 联动。 */
    private String functionScene;

    /** 为 true 时只保留 {@code imageRelated=true} 的模板，默认 false。 */
    private boolean imageOnly;

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

    public String getKeyword() {
        return keyword;
    }

    public void setKeyword(String keyword) {
        this.keyword = keyword;
    }

    public String getSource() {
        return source;
    }

    public void setSource(String source) {
        this.source = source;
    }

    public String getCategory() {
        return category;
    }

    public void setCategory(String category) {
        this.category = category;
    }

    public String getFunctionCategory() {
        return functionCategory;
    }

    public void setFunctionCategory(String functionCategory) {
        this.functionCategory = functionCategory;
    }

    public String getFunctionScene() {
        return functionScene;
    }

    public void setFunctionScene(String functionScene) {
        this.functionScene = functionScene;
    }

    public boolean isImageOnly() {
        return imageOnly;
    }

    public void setImageOnly(boolean imageOnly) {
        this.imageOnly = imageOnly;
    }
}

