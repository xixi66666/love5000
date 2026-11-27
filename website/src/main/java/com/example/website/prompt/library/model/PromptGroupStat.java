package com.example.website.prompt.library.model;

/**
 * 一级分类的条目计数，是 meta 接口大分类列表的数据载体。
 *
 * <p>对应 {@code selectGroupCounts} 的聚合结果，以 {@code prompt_group} 为主表左连条目，
 * 因此包含尚无提示词的分类（{@code count} 为 0）；结果按 {@code sort_order} 排序，
 * 该字段只用于排序，不对外输出。</p>
 */
public class PromptGroupStat {

    private String slug;
    private String name;
    private long count;

    public String getSlug() {
        return slug;
    }

    public void setSlug(String slug) {
        this.slug = slug;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public long getCount() {
        return count;
    }

    public void setCount(long count) {
        this.count = count;
    }
}