package com.example.website.prompt.model;

import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * 某个来源在某一时刻的快照，是 {@code /api/prompt-sources} 的对外数据。
 *
 * <p>{@code status} 只有三种取值：{@code live} 表示实时抓取成功；{@code fallback} 表示使用内置摘要
 * （抓取失败、或者还没有刷新过）；{@code failed} 表示来源 id 不在白名单。{@code message} 给出原因，
 * 前端据此区分真实数据与降级数据。</p>
 *
 * <p>{@code lastFetchedAt} 是生成快照的本地时间，内置快照同样会赋值，因此不能仅凭它判断该来源
 * 是否真的抓取过。</p>
 */
public class PromptSourceSnapshot {

    private String sourceId;
    private String name;
    private String url;
    private String type;
    private List<String> tags = new ArrayList<String>();
    private String status;
    private String summary;
    private OffsetDateTime lastFetchedAt;
    private String message;

    public PromptSourceSnapshot() {
    }

    /**
     * 全量构造一个快照。
     *
     * @param sourceId      来源 id；白名单外的 id 也会被保留，用于回显用户传入了什么
     * @param name          来源展示名
     * @param url           来源地址；白名单外一般为空串
     * @param type          来源分类
     * @param tags          标签列表，允许 {@code null}（转为空列表）；会复制一份再保存
     * @param status        {@code live}、{@code fallback} 或 {@code failed}
     * @param summary       摘要文本
     * @param lastFetchedAt 生成快照的本地时间，可能为 {@code null}
     * @param message       面向使用者的说明，解释为什么是降级数据
     */
    public PromptSourceSnapshot(String sourceId,
                                String name,
                                String url,
                                String type,
                                List<String> tags,
                                String status,
                                String summary,
                                OffsetDateTime lastFetchedAt,
                                String message) {
        this.sourceId = sourceId;
        this.name = name;
        this.url = url;
        this.type = type;
        this.tags = tags == null ? new ArrayList<String>() : new ArrayList<String>(tags);
        this.status = status;
        this.summary = summary;
        this.lastFetchedAt = lastFetchedAt;
        this.message = message;
    }

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

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public String getSummary() {
        return summary;
    }

    public void setSummary(String summary) {
        this.summary = summary;
    }

    public OffsetDateTime getLastFetchedAt() {
        return lastFetchedAt;
    }

    public void setLastFetchedAt(OffsetDateTime lastFetchedAt) {
        this.lastFetchedAt = lastFetchedAt;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }
}
