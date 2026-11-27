package com.example.imagetemplate.model;

/**
 * 精选库与大库的聚合状态快照。
 *
 * <p>由 {@code ImagePromptTemplateService} 在启动装配时计算一次：只要收集到任何异常信息
 * （精选加载失败、条数不符预期、大库解析失败、存在无效条目），{@code status} 就置为
 * {@code DEGRADED}，否则为 {@code READY}。状态明细进入 {@code /meta} 的 {@code status}，
 * 状态字符串另外进入列表响应的 {@code libraryStatus}，页面据此显示「预期 / 实际」数量，
 * 而不是静默只展示部分数据。</p>
 *
 * <p>{@code message} 是给人看的中文短句，多项之间用「；」拼接；即使降级，接口仍会正常
 * 返回已加载的数据。注意区分：本类的实例是状态明细，实例里的 {@code status}
 * 字段才是 {@code READY}/{@code DEGRADED} 字符串。</p>
 */
public class LibraryAggregationStatus {

    /** 状态字符串：{@code READY} 或 {@code DEGRADED}；只有完全符合预期时才是 READY。 */
    private String status;

    /** 精选模板预期条数，当前为 47。 */
    private int expectedCuratedCount;

    /** 实际加载的精选条数；加载失败时为 0。 */
    private int loadedCuratedCount;

    /** 大库预期有效条数，当前为 4409。 */
    private int expectedLibraryCount;

    /** 实际通过校验（标题与 prompt 均非空）的大库条目数。 */
    private int loadedLibraryCount;

    /** 实际聚合总数 = loadedCuratedCount + loadedLibraryCount。 */
    private int total;

    /** 中文告警汇总，多项以「；」拼接；无异常时为空串。 */
    private String message;

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public int getExpectedCuratedCount() {
        return expectedCuratedCount;
    }

    public void setExpectedCuratedCount(int expectedCuratedCount) {
        this.expectedCuratedCount = expectedCuratedCount;
    }

    public int getLoadedCuratedCount() {
        return loadedCuratedCount;
    }

    public void setLoadedCuratedCount(int loadedCuratedCount) {
        this.loadedCuratedCount = loadedCuratedCount;
    }

    public int getExpectedLibraryCount() {
        return expectedLibraryCount;
    }

    public void setExpectedLibraryCount(int expectedLibraryCount) {
        this.expectedLibraryCount = expectedLibraryCount;
    }

    public int getLoadedLibraryCount() {
        return loadedLibraryCount;
    }

    public void setLoadedLibraryCount(int loadedLibraryCount) {
        this.loadedLibraryCount = loadedLibraryCount;
    }

    public int getTotal() {
        return total;
    }

    public void setTotal(int total) {
        this.total = total;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }
}

