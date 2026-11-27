package com.example.imagetemplate.model;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 聚合后的模板模型：既是精选 JSON 的反序列化目标，也是大库适配后的统一结构。
 *
 * <p>数据来源有两条：{@code templates/image-prompt-templates.json} 直接映射为本类；
 * Prompt Console 大库经 {@code ImagePromptTemplateAdapter} 转换成同结构后合并。
 * 聚合阶段 {@code ImagePromptTemplateService} 会补齐派生字段：
 * {@code sourceId}/{@code sourceName}、{@code templateKind}、功能分类，以及
 * {@code imageRelated}/{@code curated}。因此不要在别处重复推断这些值。</p>
 *
 * <p>列表接口不直接返回本类，而是投影成 {@code ImageTemplateSummaryResponse}；
 * 详情接口才完整序列化，包含 {@code promptTemplate} 与 {@code jsonTemplate}。</p>
 */
public class ImagePromptTemplate {

    /** 全局唯一 ID；精选为手写小写 slug，大库为 {@code library-<来源>-<原始id>-<指纹>}，重复内容追加序号。 */
    private String id;

    /** 标题；大库条目要求非空，否则加载时被计为无效条目。 */
    private String title;

    /** 原始分类中文名；大库分类为空时由适配层兜底为「其他」。 */
    private String category;

    /** 原始分类 slug；精选手工维护，大库由分类名哈希生成以保证每次构建一致。 */
    private String categorySlug;

    /** 列表摘要；大库由 prompt 压缩空白后截断到 180 字符，精选直接取数据文件里的 summary。 */
    private String summary;

    /** 标签，默认空列表；参与关键词匹配与图片相关性判定。 */
    private List<String> tags = new ArrayList<String>();

    /** 结构化模板（字段名到默认值的映射）；{@code DIRECT} 模板为空 Map，渲染时不做 JSON 展开。 */
    private Map<String, Object> jsonTemplate = new LinkedHashMap<String, Object>();

    /** 自然语言模板；{@code DIRECT} 模板直接作为最终 prompt，结构化模板作为写作参考。 */
    private String promptTemplate;

    /** 来源链接，用于溯源展示；精选模板可能为空。 */
    private String sourceUrl;

    /** 来源 ID；精选固定为 {@code curated}，大库取条目的 sourceId，同时用于来源筛选。 */
    private String sourceId;

    /** 来源展示名；精选固定为「精选模板」，大库缺名时回退到 sourceId。 */
    private String sourceName;

    /** 一级功能中文名，由分类器在聚合阶段写入。 */
    private String functionCategory;

    /** 一级功能 slug，由分类器在聚合阶段写入，对应 {@code functionCategory} 查询参数。 */
    private String functionCategorySlug;

    /** 二级场景中文名，由分类器在聚合阶段写入。 */
    private String functionScene;

    /** 二级场景 slug，由分类器在聚合阶段写入，对应 {@code functionScene} 查询参数。 */
    private String functionSceneSlug;

    /** 模板类型：{@code DIRECT} 直接提示词或 {@code STRUCTURED} 结构化模板；大库条目一律为 DIRECT。 */
    private String templateKind;

    /** 是否图片相关；精选恒为 true，大库三个图片专用来源恒为 true，其余看分类与标签关键词。 */
    private boolean imageRelated;

    /** 是否精选模板；由大库适配而来的条目恒为 false。 */
    private boolean curated;

    public String getId() {
        return id;
    }

    public void setId(String id) {
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

    public String getCategorySlug() {
        return categorySlug;
    }

    public void setCategorySlug(String categorySlug) {
        this.categorySlug = categorySlug;
    }

    public String getSummary() {
        return summary;
    }

    public void setSummary(String summary) {
        this.summary = summary;
    }

    public List<String> getTags() {
        return tags;
    }

    public void setTags(List<String> tags) {
        this.tags = tags;
    }

    public Map<String, Object> getJsonTemplate() {
        return jsonTemplate;
    }

    public void setJsonTemplate(Map<String, Object> jsonTemplate) {
        this.jsonTemplate = jsonTemplate;
    }

    public String getPromptTemplate() {
        return promptTemplate;
    }

    public void setPromptTemplate(String promptTemplate) {
        this.promptTemplate = promptTemplate;
    }

    public String getSourceUrl() {
        return sourceUrl;
    }

    public void setSourceUrl(String sourceUrl) {
        this.sourceUrl = sourceUrl;
    }

    public String getSourceId() {
        return sourceId;
    }

    public void setSourceId(String sourceId) {
        this.sourceId = sourceId;
    }

    public String getSourceName() {
        return sourceName;
    }

    public void setSourceName(String sourceName) {
        this.sourceName = sourceName;
    }

    public String getFunctionCategory() {
        return functionCategory;
    }

    public void setFunctionCategory(String functionCategory) {
        this.functionCategory = functionCategory;
    }

    public String getFunctionCategorySlug() {
        return functionCategorySlug;
    }

    public void setFunctionCategorySlug(String functionCategorySlug) {
        this.functionCategorySlug = functionCategorySlug;
    }

    public String getFunctionScene() {
        return functionScene;
    }

    public void setFunctionScene(String functionScene) {
        this.functionScene = functionScene;
    }

    public String getFunctionSceneSlug() {
        return functionSceneSlug;
    }

    public void setFunctionSceneSlug(String functionSceneSlug) {
        this.functionSceneSlug = functionSceneSlug;
    }

    public String getTemplateKind() {
        return templateKind;
    }

    public void setTemplateKind(String templateKind) {
        this.templateKind = templateKind;
    }

    public boolean isImageRelated() {
        return imageRelated;
    }

    public void setImageRelated(boolean imageRelated) {
        this.imageRelated = imageRelated;
    }

    public boolean isCurated() {
        return curated;
    }

    public void setCurated(boolean curated) {
        this.curated = curated;
    }
}

