package com.example.imagetemplate.service;

import com.example.imagetemplate.model.ImagePromptTemplate;
import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.HashMap;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

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
