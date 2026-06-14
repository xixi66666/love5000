package com.example.website.prompt.service;

import com.example.website.prompt.model.PromptSourceSnapshot;
import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class PromptSourceRefreshLiveTest {

    @Test
    void refreshWhitelistedSourceUsesLiveContentWhenFetchSucceeds() {
        PromptSourceRegistry registry = new PromptSourceRegistry();
        PromptSourceFetchService service = new PromptSourceFetchService(
                registry,
                new PromptSourceSummaryService(),
                url -> "<html><head><title>Prompt123</title></head><body>提示词网站，AI 绘画提示词，视频提示词，角色提示词，摄影提示词。</body></html>");

        List<PromptSourceSnapshot> snapshots = service.refresh(Arrays.asList("prompt123"));

        assertThat(snapshots).hasSize(1);
        assertThat(snapshots.get(0).getStatus()).isEqualTo("live");
        assertThat(snapshots.get(0).getSummary()).contains("Prompt123");
        assertThat(snapshots.get(0).getSummary()).contains("AI 绘画提示词");
    }

    @Test
    void refreshWhitelistedSourceFallsBackWhenFetchFails() {
        PromptSourceRegistry registry = new PromptSourceRegistry();
        PromptSourceFetchService service = new PromptSourceFetchService(
                registry,
                new PromptSourceSummaryService(),
                url -> {
                    throw new IllegalStateException("network unavailable");
                });

        List<PromptSourceSnapshot> snapshots = service.refresh(Arrays.asList("prompt123"));

        assertThat(snapshots).hasSize(1);
        assertThat(snapshots.get(0).getStatus()).isEqualTo("fallback");
        assertThat(snapshots.get(0).getMessage()).contains("network unavailable");
    }
}
