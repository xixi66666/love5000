package com.example.website.prompt.service;

import com.example.website.prompt.model.PromptSource;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 提示词来源白名单 {@link PromptSourceRegistry} 的常量测试。
 *
 * <p>固定白名单的 ID 与顺序（控制台下拉、抓取接口和前端都按这个顺序展示），
 * 并确认 {@code findSource} 对未知 ID 返回 {@code null} 而不抛异常；
 * {@code defaultSnapshot} 对合法来源给出 {@code fallback} 状态与内置摘要。
 * 白名单是唯一可信来源，未知 ID 一律不抓取，避免本服务被当成任意 URL 代理。</p>
 *
 * <p>隔离：纯内存对象，不起 Spring、不联网、不连 MySQL。</p>
 */
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
