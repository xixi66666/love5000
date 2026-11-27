package com.example.imagetemplate.dto;

import com.example.imagetemplate.model.ImagePromptTemplate;

import java.util.ArrayList;
import java.util.List;

/**
 * 模板列表里的单条摘要，是 {@link ImagePromptTemplate} 的只读投影。
 *
 * <p>故意省略 {@code promptTemplate}、{@code jsonTemplate} 与 {@code sourceUrl}：大库正文
 * 很长，列表页一次几十条会把响应放大到不可接受。字段全部由
 * {@link #from(ImagePromptTemplate)} 赋值，且不提供 setter，避免调用方反向修改聚合缓存。</p>
 */
public class ImageTemplateSummaryResponse {

    /** 模板唯一 ID；精选为手写 slug，大库为 {@code library-} 前缀的稳定指纹 ID。 */
    private String id;

    /** 模板标题，直接用于结果卡片主文案。 */
    private String title;

    /** 摘要：精选取数据文件里的 summary，大库由 prompt 压缩空白后截断到 180 字符（含省略号）。 */
    private String summary;

    /** 原始分类中文名，例如「商业与电商」；大库分类为空时由适配层兜底为「其他」。 */
    private String category;

    /** 原始分类 slug；大库分类的 slug 由分类名哈希生成（{@code library-category-<12位哈希>}）。 */
    private String categorySlug;

    /** 标签列表，可能为空但不会是 {@code null}。 */
    private List<String> tags = new ArrayList<String>();

    /** 来源 ID；精选模板固定为 {@code curated}。 */
    private String sourceId;

    /** 来源展示名；精选模板固定为「精选模板」。 */
    private String sourceName;

    /** 一级功能中文名，例如「编程与技术开发」。 */
    private String functionCategory;

    /** 一级功能 slug，对应 {@code functionCategory} 查询参数。 */
    private String functionCategorySlug;

    /** 二级场景中文名，属于 {@code functionCategory} 之下。 */
    private String functionScene;

    /** 二级场景 slug，对应 {@code functionScene} 查询参数。 */
    private String functionSceneSlug;

    /** 模板类型：{@code DIRECT}（直接提示词，无结构化 JSON）或 {@code STRUCTURED}（精选结构化模板）。 */
    private String templateKind;

    /** 是否图片相关；精选模板一律为 true，大库按来源、分类与标签判定。 */
    private boolean imageRelated;

    /** 是否来自 47 条精选库；false 表示由 Prompt Console 大库适配而来。 */
    private boolean curated;

    /**
     * 把内部模板模型投影为列表摘要。
     *
     * <p>{@code tags} 做了一次防御性复制：聚合后的内部列表被多处共享，直接返回会让调用方
     * 有机会改到缓存。其余字段是字符串或布尔值，直接赋值。</p>
     *
     * @param template 聚合后的模板，不为 {@code null}
     * @return 只含展示字段的摘要对象
     */
    public static ImageTemplateSummaryResponse from(ImagePromptTemplate template) {
        ImageTemplateSummaryResponse response = new ImageTemplateSummaryResponse();
        response.id = template.getId();
        response.title = template.getTitle();
        response.summary = template.getSummary();
        response.category = template.getCategory();
        response.categorySlug = template.getCategorySlug();
        response.tags = template.getTags() == null
                ? new ArrayList<String>()
                : new ArrayList<String>(template.getTags());
        response.sourceId = template.getSourceId();
        response.sourceName = template.getSourceName();
        response.functionCategory = template.getFunctionCategory();
        response.functionCategorySlug = template.getFunctionCategorySlug();
        response.functionScene = template.getFunctionScene();
        response.functionSceneSlug = template.getFunctionSceneSlug();
        response.templateKind = template.getTemplateKind();
        response.imageRelated = template.isImageRelated();
        response.curated = template.isCurated();
        return response;
    }

    public String getId() {
        return id;
    }

    public String getTitle() {
        return title;
    }

    public String getSummary() {
        return summary;
    }

    public String getCategory() {
        return category;
    }

    public String getCategorySlug() {
        return categorySlug;
    }

    public List<String> getTags() {
        return tags;
    }

    public String getSourceId() {
        return sourceId;
    }

    public String getSourceName() {
        return sourceName;
    }

    public String getFunctionCategory() {
        return functionCategory;
    }

    public String getFunctionCategorySlug() {
        return functionCategorySlug;
    }

    public String getFunctionScene() {
        return functionScene;
    }

    public String getFunctionSceneSlug() {
        return functionSceneSlug;
    }

    public String getTemplateKind() {
        return templateKind;
    }

    public boolean isImageRelated() {
        return imageRelated;
    }

    public boolean isCurated() {
        return curated;
    }
}

