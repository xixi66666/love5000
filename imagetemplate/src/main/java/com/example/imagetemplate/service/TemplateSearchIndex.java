package com.example.imagetemplate.service;

import com.example.imagetemplate.model.ImagePromptTemplate;

import java.util.Locale;

/**
 * 单条模板的预计算、不可变检索字段。
 *
 * <p>在聚合阶段（{@link ImagePromptTemplateService} 构造时）构建一次，把关键词堆栈与
 * 各筛选维度的小写化结果固化下来，使列表页每次请求只做 {@code contains}/{@code equals}，
 * 不再重复拼接字符串或转小写。4456 条模板的过滤退化为一次线性扫描，
 * 代价只与模板条数成正比。</p>
 *
 * <p>所有 {@code matches*} 方法都接收“已归一化”的查询值（去空白、小写），
 * 调用方必须先完成归一化，否则大小写不一致会漏命中。分类、功能与场景维度同时
 * 接受 slug 与中文名，兼容前端新旧参数。</p>
 */
final class TemplateSearchIndex {

    /** 关键词检索的全文堆栈：标题、摘要、分类、来源名、Prompt 与标签的小写拼接。 */
    private final String normalizedKeywordHaystack;

    /** 来源 ID（精选为 {@code curated}）的小写形式。 */
    private final String normalizedSourceId;

    /** 原始分类 slug 的小写形式。 */
    private final String normalizedCategorySlug;

    /** 原始分类中文名的小写形式，兼容旧的按分类名筛选。 */
    private final String normalizedCategoryName;

    /** 一级功能 slug 的小写形式。 */
    private final String normalizedFunctionCategorySlug;

    /** 一级功能中文名的小写形式。 */
    private final String normalizedFunctionCategoryName;

    /** 二级场景 slug 的小写形式。 */
    private final String normalizedFunctionSceneSlug;

    /** 二级场景中文名的小写形式。 */
    private final String normalizedFunctionSceneName;

    /**
     * 为一条已完成功能分类的模板预计算检索字段。
     *
     * @param template 聚合后的模板，其功能分类字段必须已写入
     */
    TemplateSearchIndex(ImagePromptTemplate template) {
        this.normalizedKeywordHaystack = normalize(buildKeywordHaystack(template));
        this.normalizedSourceId = normalize(template.getSourceId());
        this.normalizedCategorySlug = normalize(template.getCategorySlug());
        this.normalizedCategoryName = normalize(template.getCategory());
        this.normalizedFunctionCategorySlug = normalize(template.getFunctionCategorySlug());
        this.normalizedFunctionCategoryName = normalize(template.getFunctionCategory());
        this.normalizedFunctionSceneSlug = normalize(template.getFunctionSceneSlug());
        this.normalizedFunctionSceneName = normalize(template.getFunctionScene());
    }

    /**
     * 关键词子串匹配。
     *
     * <p>在预拼的全文堆栈上做包含判断，中文不需要分词，因此“海报”这类短词
     * 也能命中标题或标签中的片段。</p>
     *
     * @param normalizedKeyword 已归一化的关键词，非空
     * @return {@code true} 表示命中
     */
    boolean matchesKeyword(String normalizedKeyword) {
        return normalizedKeywordHaystack.contains(normalizedKeyword);
    }

    /**
     * 来源精确匹配。
     *
     * @param normalizedSource 已归一化的来源 ID
     * @return {@code true} 表示该模板来自此来源
     */
    boolean matchesSource(String normalizedSource) {
        return normalizedSourceId.equals(normalizedSource);
    }

    /**
     * 原始分类匹配：slug 或中文名任一相等即命中。
     *
     * @param normalizedCategory 已归一化的分类 slug 或中文名
     * @return {@code true} 表示命中
     */
    boolean matchesCategory(String normalizedCategory) {
        return normalizedCategorySlug.equals(normalizedCategory)
                || normalizedCategoryName.equals(normalizedCategory);
    }

    /**
     * 一级功能匹配：slug 或中文名任一相等即命中。
     *
     * @param normalizedCategory 已归一化的一级功能 slug 或中文名
     * @return {@code true} 表示命中
     */
    boolean matchesFunctionCategory(String normalizedCategory) {
        return normalizedFunctionCategorySlug.equals(normalizedCategory)
                || normalizedFunctionCategoryName.equals(normalizedCategory);
    }

    /**
     * 二级场景匹配：slug 或中文名任一相等即命中。
     *
     * @param normalizedScene 已归一化的二级场景 slug 或中文名
     * @return {@code true} 表示命中
     */
    boolean matchesFunctionScene(String normalizedScene) {
        return normalizedFunctionSceneSlug.equals(normalizedScene)
                || normalizedFunctionSceneName.equals(normalizedScene);
    }

    /**
     * 拼接关键词检索全文。
     *
     * <p>包含标题、摘要、分类、来源名、完整 Prompt 与全部标签，字段之间以空格分隔，
     * 避免相邻字段拼接出原本不存在的词。该字符串只在构造期生成一次，
     * 不会在每次请求或功能分类时重新扫描 Prompt。</p>
     *
     * @param template 模板
     * @return 未归一化的全文堆栈
     */
    private static String buildKeywordHaystack(ImagePromptTemplate template) {
        StringBuilder haystack = new StringBuilder();
        haystack.append(template.getTitle()).append(' ')
                .append(template.getSummary()).append(' ')
                .append(template.getCategory()).append(' ')
                .append(template.getSourceName()).append(' ')
                .append(template.getPromptTemplate());
        if (template.getTags() != null) {
            for (String tag : template.getTags()) {
                haystack.append(' ').append(tag);
            }
        }
        return haystack.toString();
    }

    /**
     * 归一化待匹配文本：去首尾空白并转小写。
     *
     * <p>使用 {@link Locale#ROOT}，与查询侧归一化保持一致，避免区域相关的
     * 大小写规则造成同一关键词匹配结果不同。{@code null} 归一为空串，
     * 使 {@code equals}/{@code contains} 不必额外判空。</p>
     *
     * @param value 原始文本，可为 {@code null}
     * @return 归一化结果；{@code null} 返回空串
     */
    private static String normalize(String value) {
        return value == null ? "" : value.trim().toLowerCase(Locale.ROOT);
    }
}
