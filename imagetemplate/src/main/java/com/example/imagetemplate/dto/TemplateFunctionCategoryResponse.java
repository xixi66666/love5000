package com.example.imagetemplate.dto;

import java.util.ArrayList;
import java.util.List;

/**
 * 一级功能及下属二级场景的计数响应，构成 {@code /meta} 的功能导航树。
 *
 * <p>结构固定取自 {@code TemplateFunctionClassifier} 的分类目录：即使某个功能当前没有
 * 模板也会以 count=0 出现，保证导航不会随数据波动而消失。</p>
 */
public class TemplateFunctionCategoryResponse {

    /** 一级功能中文名，例如「视觉设计与图片」。 */
    private String name;

    /** 一级功能 slug，对应 {@code functionCategory} 查询参数。 */
    private String slug;

    /** 该功能下的模板总数；正常情况下等于 {@code scenes} 各 count 之和。 */
    private int count;

    /** 二级场景列表，按分类目录定义顺序排列，可能为空但不会是 {@code null}。 */
    private List<TemplateFunctionSceneResponse> scenes =
            new ArrayList<TemplateFunctionSceneResponse>();

    public TemplateFunctionCategoryResponse() {
    }

    public TemplateFunctionCategoryResponse(String name,
                                            String slug,
                                            int count,
                                            List<TemplateFunctionSceneResponse> scenes) {
        this.name = name;
        this.slug = slug;
        this.count = count;
        this.scenes = scenes;
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

    public List<TemplateFunctionSceneResponse> getScenes() {
        return scenes;
    }

    public void setScenes(List<TemplateFunctionSceneResponse> scenes) {
        this.scenes = scenes;
    }
}

