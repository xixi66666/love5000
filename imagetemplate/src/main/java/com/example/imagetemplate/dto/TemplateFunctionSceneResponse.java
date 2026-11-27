package com.example.imagetemplate.dto;

/**
 * 二级场景计数，挂在一级功能 {@link TemplateFunctionCategoryResponse} 之下。
 *
 * <p>与一级功能一致：分类目录里声明过的场景即使没有模板也会以 count=0 返回。
 * 查询时把 {@code functionScene} 设为这里的 slug 即可筛选。</p>
 */
public class TemplateFunctionSceneResponse {

    /** 场景中文名，例如「代码解释与重构」。 */
    private String name;

    /** 场景 slug，对应 {@code functionScene} 查询参数。 */
    private String slug;

    /** 该场景下的模板条数。 */
    private int count;

    public TemplateFunctionSceneResponse() {
    }

    public TemplateFunctionSceneResponse(String name, String slug, int count) {
        this.name = name;
        this.slug = slug;
        this.count = count;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getSlug() {
        return slug;
    }

    public void setSlug(String slug) {
        this.slug = slug;
    }

    public int getCount() {
        return count;
    }

    public void setCount(int count) {
        this.count = count;
    }
}

