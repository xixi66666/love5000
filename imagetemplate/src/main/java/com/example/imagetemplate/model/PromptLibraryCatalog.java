package com.example.imagetemplate.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

import java.util.ArrayList;
import java.util.List;

@JsonIgnoreProperties(ignoreUnknown = true)
/**
 * Prompt Console 大库 JSON（{@code templates/prompt-console/prompt-library.json}）的根结构。
 *
 * <p>该文件的唯一源在 website 模块，Maven 构建时复制进本模块 classpath；本类只用于
 * 反序列化读取，不回写。{@code @JsonIgnoreProperties} 让上游新增字段时本服务不至于
 * 启动失败。</p>
 */
public class PromptLibraryCatalog {

    /** 大库生成时间戳（原样字符串），仅用于排障，不参与任何业务判断。 */
    private String generatedAt;

    /** 来源授权标记，由生成流程写入；当前只做记录，不参与过滤。 */
    private boolean authorizedByUser;

    /** 来源元数据列表，默认空列表；加载器会把 {@code null} 归一为空列表。 */
    private List<PromptLibrarySource> sources = new ArrayList<PromptLibrarySource>();

    /** 提示词条目列表；总数应与 4409 一致，否则聚合状态降级。 */
    private List<PromptLibraryEntry> entries = new ArrayList<PromptLibraryEntry>();

    public String getGeneratedAt() {
        return generatedAt;
    }

    public void setGeneratedAt(String generatedAt) {
        this.generatedAt = generatedAt;
    }

    public boolean isAuthorizedByUser() {
        return authorizedByUser;
    }

    public void setAuthorizedByUser(boolean authorizedByUser) {
        this.authorizedByUser = authorizedByUser;
    }

    public List<PromptLibrarySource> getSources() {
        return sources;
    }

    public void setSources(List<PromptLibrarySource> sources) {
        this.sources = sources;
    }

    public List<PromptLibraryEntry> getEntries() {
        return entries;
    }

    public void setEntries(List<PromptLibraryEntry> entries) {
        this.entries = entries;
    }
}

