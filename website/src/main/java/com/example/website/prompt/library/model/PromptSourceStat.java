package com.example.website.prompt.library.model;

/**
 * 来源的条目计数与展示字段，是 meta 接口来源列表的数据载体。
 *
 * <p>对应 {@code selectSourceStats} 的聚合结果：从 {@code prompt_source} 左连条目，按来源自增
 * id 排序，因此没有条目的来源也会出现（{@code count} 为 0）。{@code status} 是来源自身状态
 * （例如 {@code imported}），与单条提示词的 {@code status} 无关；{@code url} 只用于展示，
 * 前端不会拿它去抓取内容。</p>
 */
public class PromptSourceStat {

    private String sourceId;
    private String name;
    private String url;
    private String license;
    private String summary;
    private String status;
    private long count;

    public String getSourceId() {
        return sourceId;
    }

    public void setSourceId(String sourceId) {
        this.sourceId = sourceId;
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
}