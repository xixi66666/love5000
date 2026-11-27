package com.example.imagetemplate.model;

/**
 * 一次功能分类的结果，是不可变值对象。
 *
 * <p>由 {@code TemplateFunctionClassifier} 产出，{@code ImagePromptTemplateService}
 * 在聚合阶段把四个字段写回 {@link ImagePromptTemplate}。名称与 slug 成对返回，
 * 前端既能展示中文又能直接回传 slug 做筛选，不必再反查分类目录。
 * 本类只有 getter、字段全部 final，构造后可安全跨线程共享。</p>
 */
public final class TemplateFunctionClassification {

    /** 一级功能中文名，例如「编程与技术开发」。 */
    private final String categoryName;

    /** 一级功能 slug，直接用于 {@code functionCategory} 查询参数。 */
    private final String categorySlug;

    /** 二级场景中文名，例如「代码解释与重构」。 */
    private final String sceneName;

    /** 二级场景 slug，直接用于 {@code functionScene} 查询参数。 */
    private final String sceneSlug;

    public TemplateFunctionClassification(String categoryName,
                                          String categorySlug,
                                          String sceneName,
                                          String sceneSlug) {
        this.categoryName = categoryName;
        this.categorySlug = categorySlug;
        this.sceneName = sceneName;
        this.sceneSlug = sceneSlug;
    }

    public String getCategoryName() {
        return categoryName;
    }

    public String getCategorySlug() {
        return categorySlug;
    }

    public String getSceneName() {
        return sceneName;
    }

    public String getSceneSlug() {
        return sceneSlug;
    }
}

