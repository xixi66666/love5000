package com.example.website.prompt.service;

import com.example.website.prompt.model.PromptSourceSnapshot;
import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 提示词来源「实时抓取」分支的测试。
 *
 * <p>类名带 Live，但并不访问外网：{@link PromptSourceFetchService} 通过三参构造器注入固定的
 * 抓取函数，分别模拟成功（返回一段 HTML）和失败（抛异常）。成功时快照状态为 {@code live}，
 * 摘要由 {@link PromptSourceSummaryService} 从 HTML 里提炼出标题与关键词；失败时降级为
 * 白名单自带的 {@code fallback} 摘要，并把异常消息记进 {@code message}，
 * 保证页面拿到可用内容而不是空列表。</p>
 *
 * <p>隔离：抓取函数是 lambda 替身，不联网；不连数据库、不起 Spring 上下文。</p>
 */
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
