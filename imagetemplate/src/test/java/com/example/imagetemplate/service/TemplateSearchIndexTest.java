package com.example.imagetemplate.service;

import com.example.imagetemplate.model.ImagePromptTemplate;
import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.HashMap;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * {@link TemplateSearchIndex} 的预归一化与匹配测试。
 *
 * <p>索引在构造时把标题、摘要、分类、来源、功能层级、Prompt 正文与标签拼成小写检索文本，
 * 因此中文原样匹配、ASCII 忽略大小写，来源与分类的 slug 和中文名都能命中；空查询等于不做
 * 过滤，缺失字段按空串处理。用例还用 {@link CountingTemplate} 统计 getter 调用次数，证明
 * 匹配阶段不再回读模型字段（构造后连续匹配 1000 次读取次数不变）。</p>
 *
 * <p>隔离手段：全部使用内存对象与计数子类夹具，不读取模板 JSON、不启动 Spring、不联网。</p>
 */
class TemplateSearchIndexTest {

    @Test
    void normalizesFieldsOnceAndMatchesChineseAndAsciiCaseInsensitively() {
        CountingTemplate template = new CountingTemplate();
        template.setId("mixed-case");
        template.setTitle("霓虹城市 头像");
        template.setSummary("森系海报");
        template.setCategory("视觉设计");
        template.setCategorySlug("Visual-Design");
        template.setSourceId("Curated");
        template.setSourceName("精选模板");
        template.setFunctionCategory("视觉创作");
        template.setFunctionCategorySlug("visual-creation");
        template.setFunctionScene("头像摄影");
        template.setFunctionSceneSlug("portrait-photo");
        template.setPromptTemplate("水墨 山水 " + "Cyan");
        template.setTags(Arrays.asList("Cyan", "夜景"));

        TemplateSearchIndex index = new TemplateSearchIndex(template);
        int readsAfterBuild = template.totalReads();

        assertThat(readsAfterBuild).isGreaterThan(0);
        assertThat(index.matchesKeyword("水墨")).isTrue();
        assertThat(index.matchesKeyword("cyan")).isTrue();
        assertThat(index.matchesKeyword("霓虹城市")).isTrue();
        assertThat(index.matchesKeyword("夜景")).isTrue();
        assertThat(index.matchesKeyword("不存在")).isFalse();
        assertThat(index.matchesSource("curated")).isTrue();
        assertThat(index.matchesSource("prompt123")).isFalse();
        assertThat(index.matchesCategory("visual-design")).isTrue();
        assertThat(index.matchesCategory("视觉设计")).isTrue();
        assertThat(index.matchesFunctionCategory("visual-creation")).isTrue();
        assertThat(index.matchesFunctionCategory("视觉创作")).isTrue();
        assertThat(index.matchesFunctionScene("portrait-photo")).isTrue();
        assertThat(index.matchesFunctionScene("头像摄影")).isTrue();

        // 连续匹配 1000 次，读取次数必须保持不变，证明匹配阶段只查构造时预归一化的文本。
        for (int i = 0; i < 1000; i++) {
            index.matchesKeyword("水墨");
            index.matchesSource("curated");
            index.matchesCategory("视觉设计");
            index.matchesFunctionCategory("visual-creation");
            index.matchesFunctionScene("头像摄影");
        }

        assertThat(template.totalReads()).isEqualTo(readsAfterBuild);
    }

    @Test
    void treatsMissingSearchableFieldsAsEmptyValues() {
        ImagePromptTemplate template = new ImagePromptTemplate();
        TemplateSearchIndex index = new TemplateSearchIndex(template);

        assertThat(index.matchesKeyword("")).isTrue();
        assertThat(index.matchesSource("")).isTrue();
        assertThat(index.matchesCategory("")).isTrue();
        assertThat(index.matchesFunctionCategory("")).isTrue();
        assertThat(index.matchesFunctionScene("")).isTrue();
        assertThat(index.matchesKeyword("头像")).isFalse();
    }

    /**
     * 统计各字段 getter 被调用次数的模板子类。
     *
     * <p>用于区分“构造索引时读取一次”和“每次匹配都重新读取”两种实现；若匹配阶段仍在访问
     * 模型，循环 1000 次后读取次数会增长，用例即可发现性能回归。</p>
     */
    private static final class CountingTemplate extends ImagePromptTemplate {

        private final Map<String, Integer> reads = new HashMap<String, Integer>();

        @Override
        public String getTitle() {
            count("title");
            return super.getTitle();
        }

        @Override
        public String getSummary() {
            count("summary");
            return super.getSummary();
        }

        @Override
        public String getCategory() {
            count("category");
            return super.getCategory();
        }

        @Override
        public String getCategorySlug() {
            count("categorySlug");
            return super.getCategorySlug();
        }

        @Override
        public String getSourceId() {
            count("sourceId");
            return super.getSourceId();
        }

        @Override
        public String getSourceName() {
            count("sourceName");
            return super.getSourceName();
        }

        @Override
        public String getFunctionCategory() {
            count("functionCategory");
            return super.getFunctionCategory();
        }

        @Override
        public String getFunctionCategorySlug() {
            count("functionCategorySlug");
            return super.getFunctionCategorySlug();
        }

        @Override
        public String getFunctionScene() {
            count("functionScene");
            return super.getFunctionScene();
        }

        @Override
        public String getFunctionSceneSlug() {
            count("functionSceneSlug");
            return super.getFunctionSceneSlug();
        }

        @Override
        public String getPromptTemplate() {
            count("promptTemplate");
            return super.getPromptTemplate();
        }

        @Override
        public java.util.List<String> getTags() {
            count("tags");
            return super.getTags();
        }

        int totalReads() {
            int total = 0;
            for (Integer value : reads.values()) {
                total += value;
            }
            return total;
        }

        private void count(String field) {
            Integer value = reads.get(field);
            reads.put(field, value == null ? 1 : value + 1);
        }
    }
}
