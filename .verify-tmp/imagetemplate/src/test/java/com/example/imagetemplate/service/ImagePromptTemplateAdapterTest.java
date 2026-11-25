package com.example.imagetemplate.service;

import com.example.imagetemplate.model.ImagePromptTemplate;
import com.example.imagetemplate.model.PromptLibraryEntry;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class ImagePromptTemplateAdapterTest {

    private ImagePromptTemplateAdapter adapter;

    @BeforeEach
    void setUp() {
        adapter = new ImagePromptTemplateAdapter();
    }

    @Test
    void adaptsEveryRowAndMakesExactDuplicatesAddressable() {
        PromptLibraryEntry imageEntry = entry(
                "same-id",
                "youmind-awesome-gpt-image-2",
                "YouMind GPT Image 2",
                "海报",
                "生成一张黑金电影海报");
        PromptLibraryEntry textEntry = entry(
                "text-id",
                "prompt123",
                "Prompt123",
                "写作",
                "帮助我制定一份文章写作计划");

        List<ImagePromptTemplate> adapted =
                adapter.adapt(Arrays.asList(imageEntry, imageEntry, textEntry));

        assertThat(adapted).hasSize(3);
        assertThat(adapted).extracting("id").doesNotHaveDuplicates();
        assertThat(adapted.get(0).getId())
                .startsWith("library-youmind-awesome-gpt-image-2-same-id-");
        assertThat(adapted.get(1).getId()).endsWith("-2");
        assertThat(adapted.get(0).getTemplateKind()).isEqualTo("DIRECT");
        assertThat(adapted.get(0).isImageRelated()).isTrue();
        assertThat(adapted.get(0).isCurated()).isFalse();
        assertThat(adapted.get(0).getJsonTemplate()).isEmpty();
        assertThat(adapted.get(2).isImageRelated()).isFalse();
    }

    @Test
    void stableContentProducesStableId() {
        PromptLibraryEntry imageEntry = entry(
                "stable-id",
                "evolink-awesome-gpt-image-2-prompts",
                "EvoLinkAI",
                "摄影",
                "电影感摄影提示词");

        String first = adapter.adapt(Collections.singletonList(imageEntry)).get(0).getId();
        String second = adapter.adapt(Collections.singletonList(imageEntry)).get(0).getId();

        assertThat(first).isEqualTo(second);
    }

    @Test
    void imageKeywordsInCategoryOrTagsMarkGeneralSourcesAsImageRelated() {
        PromptLibraryEntry entry = entry(
                "poster-id",
                "awesome-prompts",
                "awesome-prompts",
                "品牌",
                "生成活动方案");
        entry.setTags(Arrays.asList("营销", "Poster"));

        assertThat(adapter.adapt(Collections.singletonList(entry)).get(0).isImageRelated())
                .isTrue();
    }

    private PromptLibraryEntry entry(String id,
                                     String sourceId,
                                     String sourceName,
                                     String category,
                                     String prompt) {
        PromptLibraryEntry entry = new PromptLibraryEntry();
        entry.setId(id);
        entry.setSourceId(sourceId);
        entry.setSourceName(sourceName);
        entry.setSourceUrl("https://example.com/" + id);
        entry.setTitle("模板 " + id);
        entry.setCategory(category);
        entry.setTags(Collections.singletonList(category));
        entry.setPrompt(prompt);
        return entry;
    }
}
