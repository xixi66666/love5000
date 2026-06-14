package com.example.website.prompt.service;

import com.example.website.prompt.model.PromptSourceSnapshot;
import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class PromptSourceFetchServiceTest {

    private final PromptSourceRegistry registry = new PromptSourceRegistry();
    private final PromptSourceFetchService service = new PromptSourceFetchService(registry);

    @Test
    void refreshUnknownSourceReturnsFailedSnapshot() {
        List<PromptSourceSnapshot> snapshots = service.refresh(Arrays.asList("unknown-source"));

        assertThat(snapshots).hasSize(1);
        assertThat(snapshots.get(0).getSourceId()).isEqualTo("unknown-source");
        assertThat(snapshots.get(0).getStatus()).isEqualTo("failed");
        assertThat(snapshots.get(0).getMessage()).contains("not allowed");
    }

    @Test
    void listSnapshotsUsesFallbacksBeforeRefresh() {
        List<PromptSourceSnapshot> snapshots = service.listSnapshots();

        assertThat(snapshots).hasSize(6);
        assertThat(snapshots).allSatisfy(snapshot -> assertThat(snapshot.getStatus()).isEqualTo("fallback"));
    }

    @Test
    void refreshWithoutSourceIdsRefreshesAllWhitelistedSources() {
        List<PromptSourceSnapshot> snapshots = service.refresh(null);

        assertThat(snapshots).hasSize(6);
        assertThat(snapshots).extracting(PromptSourceSnapshot::getStatus).containsOnly("fallback");
    }
}
