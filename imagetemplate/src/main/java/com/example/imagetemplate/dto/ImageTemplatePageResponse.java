package com.example.imagetemplate.dto;

import java.util.ArrayList;
import java.util.List;

/**
 * 分页查询模板摘要的响应体。
 *
 * <p>只包含摘要字段，不返回 {@code promptTemplate} 与 {@code jsonTemplate}：大库正文很长，
 * 一次几十条会把响应放大到不可接受。完整内容必须走详情接口。</p>
 *
 * <p>大库降级时本对象仍然成功返回：{@code libraryStatus} 为 {@code DEGRADED}，
 * {@code message} 给出预期与实际数量，前端据此显示告警，而不是把当前列表当成完整数据。</p>
 */
public class ImageTemplatePageResponse {

    /** 恒为 true；接口层面的失败走异常处理器，不会返回本类型。 */
    private boolean success = true;

    /** 应用全部筛选条件后的命中总数（不是全库总数），用于「共 N 条」展示。 */
    private int total;

    /** 当前页码，原样回显请求值（从 1 开始）。 */
    private int page;

    /** 每页条数，原样回显请求值，默认 48、上限 100。 */
    private int size;

    /** 是否还有下一页（{@code 当前页末尾 < total}），前端据此决定「加载更多」按钮。 */
    private boolean hasMore;

    /** 聚合状态快照：{@code READY} 或 {@code DEGRADED}；后者表示精选或大库条数不符预期。 */
    private String libraryStatus;

    /** 聚合告警文本（中文，多项以「；」拼接）；正常时为空串而不是 {@code null}。 */
    private String message;

    /** 当前页的摘要列表，可能为空但不会是 {@code null}。 */
    private List<ImageTemplateSummaryResponse> templates =
            new ArrayList<ImageTemplateSummaryResponse>();

    public boolean isSuccess() {
        return success;
    }

    public int getTotal() {
        return total;
    }

    public void setTotal(int total) {
        this.total = total;
    }

    public int getPage() {
        return page;
    }

    public void setPage(int page) {
        this.page = page;
    }

    public int getSize() {
        return size;
    }

    public void setSize(int size) {
        this.size = size;
    }

    public boolean isHasMore() {
        return hasMore;
    }

    public void setHasMore(boolean hasMore) {
        this.hasMore = hasMore;
    }

    public String getLibraryStatus() {
        return libraryStatus;
    }

    public void setLibraryStatus(String libraryStatus) {
        this.libraryStatus = libraryStatus;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }

    public List<ImageTemplateSummaryResponse> getTemplates() {
        return templates;
    }

    public void setTemplates(List<ImageTemplateSummaryResponse> templates) {
        this.templates = templates;
    }
}

