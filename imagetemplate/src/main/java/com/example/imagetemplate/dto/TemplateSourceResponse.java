package com.example.imagetemplate.dto;

/**
 * 来源计数的响应投影，用于来源筛选与版权溯源。
 *
 * <p>{@code count} 是启动装配时按实际聚合结果统计的条数，不是大库文件自带的 entryCount；
 * 因此剔除无效条目后计数会自动收敛。本类只有 getter，构造后不再变化。</p>
 */
public class TemplateSourceResponse {

    /** 来源 ID；精选模板固定为 {@code curated}，对应 {@code source} 查询参数。 */
    private String id;

    /** 来源展示名；精选为「精选模板」。 */
    private String name;

    /** 来源主页或仓库地址；精选模板没有外部来源，这里是空串。 */
    private String url;

    /** 该来源下的模板条数。 */
    private int count;

    public TemplateSourceResponse() {
    }

    public TemplateSourceResponse(String id, String name, String url, int count) {
        this.id = id;
        this.name = name;
        this.url = url;
        this.count = count;
    }

    public String getId() {
        return id;
    }

    public String getName() {
        return name;
    }

    public String getUrl() {
        return url;
    }

    public int getCount() {
        return count;
    }
}

