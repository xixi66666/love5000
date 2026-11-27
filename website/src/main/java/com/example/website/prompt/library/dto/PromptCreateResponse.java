package com.example.website.prompt.library.dto;

/**
 * {@code POST /api/prompts} 成功时的响应体。
 *
 * <p>{@code success} 默认 {@code true}，失败不会走到这里——校验失败由控制器返回
 * {@code {"success":false,"message":"..."}} 的 400 响应，所以本类只描述成功形态。
 * {@code entry} 不是请求体的回显，而是插入后按新主键重新查询的完整详情，
 * 因此包含 {@code id}、推导出的 {@code groupSlug}/{@code groupName} 和 {@code sourceName}。</p>
 */
public class PromptCreateResponse {

    private boolean success = true;
    private PromptDetailResponse.EntryDetail entry;

    public boolean isSuccess() {
        return success;
    }

    public void setSuccess(boolean success) {
        this.success = success;
    }

    public PromptDetailResponse.EntryDetail getEntry() {
        return entry;
    }

    public void setEntry(PromptDetailResponse.EntryDetail entry) {
        this.entry = entry;
    }
}