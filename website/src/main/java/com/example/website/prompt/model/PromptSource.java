package com.example.website.prompt.model;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * 白名单里的一条提示词来源定义，属于只读配置对象。
 *
 * <p>实例由 {@link com.example.website.prompt.service.PromptSourceRegistry} 在启动时构造，
 * 之后只作为读模型使用。{@code tags} 在构造和 setter 里都会复制成新列表，
 * {@link #getTags()} 返回不可修改视图，避免调用方就地改掉注册表的白名单。</p>
 *
 * <p>{@code defaultSummary} 是抓取失败时的兜底摘要，必须始终可读，不能为空。</p>
 */
public class PromptSource {

    private String id;
    private String name;
    private String url;
    private String type;
    private List<String> tags = new ArrayList<String>();
    private String defaultSummary;

    public PromptSource() {
    }

    /**
     * 全量构造一个来源定义。
     *
     * @param id             来源唯一标识，同时是刷新接口的入参
     * @param name           展示名称
     * @param url            抓取地址，只在白名单内被访问
     * @param type           来源分类，例如 {@code image-generation}
     * @param tags           标签列表，允许 {@code null}（转为空列表）；会复制一份再保存
     * @param defaultSummary 抓取失败时使用的内置摘要
     */
    public PromptSource(String id, String name, String url, String type, List<String> tags, String defaultSummary) {
        this.id = id;
        this.name = name;
        this.url = url;
        this.type = type;
        this.tags = tags == null ? new ArrayList<String>() : new ArrayList<String>(tags);
        this.defaultSummary = defaultSummary;
    }

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

    public String getUrl() {
        return url;
    }

    public void setUrl(String url) {
        this.url = url;
    }

    public String getType() {
        return type;
    }

    public void setType(String type) {
        this.type = type;
    }

    public List<String> getTags() {
        return Collections.unmodifiableList(tags);
    }

    public void setTags(List<String> tags) {
        this.tags = tags == null ? new ArrayList<String>() : new ArrayList<String>(tags);
    }

    public String getDefaultSummary() {
        return defaultSummary;
    }

    public void setDefaultSummary(String defaultSummary) {
        this.defaultSummary = defaultSummary;
    }
}
