package com.example.website.prompt.dto;

import java.util.ArrayList;
import java.util.List;

/**
 * {@code POST /api/prompt-sources/refresh} 的请求体，由 Jackson 反序列化。
 *
 * <p>只有 {@code sourceIds} 一个字段：为空或整个请求体缺省时表示刷新全部白名单来源；
 * 传入的 id 如果不在 {@code PromptSourceRegistry} 的白名单里，不会抛异常，而是得到一条
 * {@code status=failed} 的快照（见 {@code PromptSourceRegistry#defaultSnapshot}）。</p>
 */
public class PromptSourceRefreshRequest {

    private List<String> sourceIds = new ArrayList<String>();

    public List<String> getSourceIds() {
        return sourceIds;
    }

    public void setSourceIds(List<String> sourceIds) {
        this.sourceIds = sourceIds == null ? new ArrayList<String>() : new ArrayList<String>(sourceIds);
    }
}
