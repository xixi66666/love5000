package com.example.website.prompt.library.model;

/**
 * 提示词库的单条记录，同时承担三个角色：{@code prompt_entry} 表行的查询结果、列表/详情映射的
 * 数据来源，以及 {@code PromptLibraryDao#insert} 的写入参数。
 *
 * <p>字段里有三组容易混淆的内容：{@code sourceName}/{@code groupName} 是 Mapper 联表
 * {@code prompt_source}/{@code prompt_group} 带出的展示名，不是表列；{@code entryKey} 是导入或
 * 手动添加时生成的业务键（手动添加固定为 {@code manual-{uuid}} 形式）；{@code tags} 是英文逗号分隔的
 * 字符串，服务端对外输出时才拆成数组。</p>
 *
 * <p>{@code preview} 只在列表查询（{@code searchPage}）里由 SQL 的 {@code left(prompt,200)} 填充，
 * 详情查询不设置该字段，完整正文始终在 {@code prompt} 中。</p>
 */
public class PromptEntry {

    private Long id;
    private String entryKey;
    private String sourceId;
    private String sourceName;
    private String title;
    private String category;
    private String groupSlug;
    private String groupName;
    private String tags;
    private String license;
    private String status;
    private String sourceUrl;
    private String prompt;
    private String preview;

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getEntryKey() {
        return entryKey;
    }

    public void setEntryKey(String entryKey) {
        this.entryKey = entryKey;
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

    public String getGroupSlug() {
        return groupSlug;
    }

    public void setGroupSlug(String groupSlug) {
        this.groupSlug = groupSlug;
    }

    public String getGroupName() {
        return groupName;
    }

    public void setGroupName(String groupName) {
        this.groupName = groupName;
    }

    public String getTags() {
        return tags;
    }

    public void setTags(String tags) {
        this.tags = tags;
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

    public String getSourceUrl() {
        return sourceUrl;
    }

    public void setSourceUrl(String sourceUrl) {
        this.sourceUrl = sourceUrl;
    }

    public String getPrompt() {
        return prompt;
    }

    public void setPrompt(String prompt) {
        this.prompt = prompt;
    }

    public String getPreview() {
        return preview;
    }

    public void setPreview(String preview) {
        this.preview = preview;
    }
}