package com.example.imagetemplate.model;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * 大库加载结果的不可变快照。
 *
 * <p>{@code PromptLibraryLoader} 在任何异常下都返回本对象而不抛出：整体解析失败时条目为空、
 * {@code errorCount=1}，原因写进 {@code message}；部分条目缺标题或 prompt 时只登记数量。
 * 上层据此决定聚合状态是否降级，因此大库损坏不会导致服务无法启动。</p>
 *
 * <p>构造时对两个列表做防御性复制并包成只读视图，{@code null} 归一为空列表，
 * 避免调用方修改内部数据或在遍历时遇到 {@code null}。本类没有 setter。</p>
 */
public class PromptLibraryLoadResult {

    /** 来源元数据，按大库文件顺序；可能为空列表，不会为 {@code null}。 */
    private final List<PromptLibrarySource> sources;

    /** 通过校验的条目；缺标题或缺 prompt 的条目已被剔除。 */
    private final List<PromptLibraryEntry> entries;

    /** 无效条目数量；整体解析失败时记为 1，便于沿用同一套「有错即降级」判断。 */
    private final int errorCount;

    /** 人类可读的加载问题汇总，多项以「；」拼接；无问题时为空串（不是 {@code null}）。 */
    private final String message;

    /**
     * 创建加载结果快照，并对两个列表做防御性复制。
     *
     * @param sources    来源列表，可为 {@code null}，内部归一为空列表
     * @param entries    有效条目列表，可为 {@code null}，内部归一为空列表
     * @param errorCount 无效条目数或整体失败标记
     * @param message    问题说明，{@code null} 时存为空串
     */
    public PromptLibraryLoadResult(List<PromptLibrarySource> sources,
                                   List<PromptLibraryEntry> entries,
                                   int errorCount,
                                   String message) {
        this.sources = immutableCopy(sources);
        this.entries = immutableCopy(entries);
        this.errorCount = errorCount;
        this.message = message == null ? "" : message;
    }

    public List<PromptLibrarySource> getSources() {
        return sources;
    }

    public List<PromptLibraryEntry> getEntries() {
        return entries;
    }

    public int getErrorCount() {
        return errorCount;
    }

    public String getMessage() {
        return message;
    }

    /**
     * 复制列表并包成只读视图。
     *
     * @param values 原始列表，可为 {@code null}
     * @param <T>    元素类型
     * @return {@code null} 对应 {@link Collections#emptyList()}，否则为与原列表解耦的不可变副本
     */
    private static <T> List<T> immutableCopy(List<T> values) {
        if (values == null) {
            return Collections.emptyList();
        }
        return Collections.unmodifiableList(new ArrayList<T>(values));
    }
}

