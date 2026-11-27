package com.example.website.prompt.library.model;

/**
 * “大分类 + 小分类”的条目计数，是 meta 接口二级分类树的数据载体。
 *
 * <p>对应 {@code selectCategoryCounts} 的聚合结果，不是数据库实体：只包含实际存在提示词的小分类，
 * 按计数降序返回，{@code groupSlug} 用于把统计行挂回所属大分类。</p>
 */
public class PromptCategoryStat {

    private String groupSlug;
    private String category;
    private long count;

    public String getGroupSlug() {
        return groupSlug;
    }

    public void setGroupSlug(String groupSlug) {
        this.groupSlug = groupSlug;
    }

    public String getCategory() {
        return category;
    }

    public void setCategory(String category) {
        this.category = category;
    }

    public long getCount() {
        return count;
    }

    public void setCount(long count) {
        this.count = count;
    }
}