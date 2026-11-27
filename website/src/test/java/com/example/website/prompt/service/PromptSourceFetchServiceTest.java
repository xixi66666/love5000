package com.example.website.prompt.service;

import com.example.website.prompt.model.PromptSourceSnapshot;
import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 提示词来源抓取服务 {@link PromptSourceFetchService} 的白名单与降级测试。
 *
 * <p>覆盖三条分支：刷新不在白名单里的 sourceId 时返回失败快照（消息含 not allowed），
 * 且不会发起请求；刷新之前 {@code listSnapshots} 返回 6 个白名单来源的 {@code fallback} 快照；
 * {@code refresh(null)} 表示刷新全部白名单。</p>
 *
 * <p>隔离：这里用单参构造器，它注入的 HTTP 客户端永远抛 {@code IllegalStateException}，
 * 所以「全部 fallback」是可重复的本地结果，而不是网络恰好不通；全程不联网、不连 MySQL。
 * 白名单数量 6 与 {@link PromptSourceRegistry} 绑定，新增来源时要同步这条断言。</p>
 */
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
