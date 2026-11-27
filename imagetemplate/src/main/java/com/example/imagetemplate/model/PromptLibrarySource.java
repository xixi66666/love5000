package com.example.imagetemplate.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

import java.util.ArrayList;
import java.util.List;

@JsonIgnoreProperties(ignoreUnknown = true)
/**
 * 大库来源的元数据。
 *
 * <p>只描述来源本身（名称、主页、授权、状态），条目不在本类聚合。注意接口返回的
 * {@code count} 由服务按实际条目重新统计，本类的 {@code entryCount} 是文件自带值，
 * 仅在排查数据差异时参考。</p>
 */
public class PromptLibrarySource {

    /** 来源 ID，与条目 sourceId 对应；也是 {@code source} 筛选参数的取值。 */
    private String id;

    /** 来源展示名，会出现在来源筛选与结果卡片上。 */
    private String name;

    /** 来源主页或仓库地址，用于版权溯源。 */
    private String url;

    /** 授权协议说明文本。 */
    private String license;

    /** 来源简介；当前未透出到接口，保留作数据说明。 */
    private String summary;

    /** 该来源覆盖的原始分类名列表，默认空列表；只作元数据，不参与筛选。 */
    private List<String> categories = new ArrayList<String>();

    /** 来源状态字符串（导入流程写入）；不参与加载是否成功的判定。 */
    private String status;

    /** 文件自带的条目数；接口展示的计数按实际聚合结果统计，不使用该值。 */
    private int entryCount;

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

    public List<String> getCategories() {
        return categories;
    }

    public void setCategories(List<String> categories) {
        this.categories = categories;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public int getEntryCount() {
        return entryCount;
    }

    public void setEntryCount(int entryCount) {
        this.entryCount = entryCount;
    }
}

