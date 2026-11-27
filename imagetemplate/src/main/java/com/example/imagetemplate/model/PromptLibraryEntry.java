package com.example.imagetemplate.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

import java.util.ArrayList;
import java.util.List;

@JsonIgnoreProperties(ignoreUnknown = true)
/**
 * 大库中的一条公开提示词。
 *
 * <p>字段对应 website 侧 {@code prompt-library.json} 的条目结构，加载后由
 * {@code ImagePromptTemplateAdapter} 转换为 {@link ImagePromptTemplate}。只有
 * {@code title} 与 {@code prompt} 都非空的条目才算有效，其余计入
 * {@link PromptLibraryLoadResult#getErrorCount()} 并在聚合状态中提示。</p>
 */
public class PromptLibraryEntry {

    /** 来源内部编号；参与生成稳定的聚合 ID，不直接对外暴露。 */
    private String id;

    /** 来源 ID；参与图片相关性判定与稳定 ID 生成。 */
    private String sourceId;

    /** 来源展示名；为空时适配层回退到 sourceId。 */
    private String sourceName;

    /** 条目原始链接，用于溯源展示。 */
    private String sourceUrl;

    /** 授权协议文本；仅做溯源展示，不参与筛选。 */
    private String license;

    /** 条目状态字符串（来自大库生成流程）；当前不参与过滤，保留以便排查。 */
    private String status;

    /** 标题；为空会导致该条目在加载阶段被丢弃。 */
    private String title;

    /** 原始分类名；为空时适配层兜底为「其他」。 */
    private String category;

    /** 标签，默认空列表；参与关键词搜索与图片相关性判定。 */
    private List<String> tags = new ArrayList<String>();

    /** 完整提示词正文；为空会导致条目被丢弃，非空时作为 DIRECT 模板的 promptTemplate。 */
    private String prompt;

    public String getId() {
        return id;
    }

    public void setId(String id) {
        this.id = id;
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

    public String getSourceUrl() {
        return sourceUrl;
    }

    public void setSourceUrl(String sourceUrl) {
        this.sourceUrl = sourceUrl;
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

    public List<String> getTags() {
        return tags;
    }

    public void setTags(List<String> tags) {
        this.tags = tags;
    }

    public String getPrompt() {
        return prompt;
    }

    public void setPrompt(String prompt) {
        this.prompt = prompt;
    }
}

