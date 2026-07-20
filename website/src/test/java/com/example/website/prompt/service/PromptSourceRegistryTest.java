package com.example.website.prompt.service;

import com.example.website.prompt.model.PromptSource;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class PromptSourceRegistryTest {

    private final PromptSourceRegistry registry = new PromptSourceRegistry();

    @Test
    void listSourcesReturnsDefaultWhitelist() {
        List<PromptSource> sources = registry.listSources();

        assertThat(sources).extracting(PromptSource::getId)
                .containsExactly(
                        "prompt123",
                        "awesome-chatgpt-prompts",
                        "awesome-prompts",
                        "youmind-awesome-gpt-image-2",
                        "freestylefly-awesome-gpt-image-2",
                        "evolink-awesome-gpt-image-2-prompts");
    }

    @Test
    void findSourceRejectsUnknownIds() {
        assertThat(registry.findSource("not-allowed")).isNull();
    }

    @Test
    void defaultSnapshotUsesFallbackSummary() {
        assertThat(registry.defaultSnapshot("prompt123").getStatus()).isEqualTo("fallback");
        assertThat(registry.defaultSnapshot("prompt123").getSummary()).contains("提示词");
    }
}
