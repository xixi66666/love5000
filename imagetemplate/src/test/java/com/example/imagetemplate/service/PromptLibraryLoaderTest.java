package com.example.imagetemplate.service;

import com.example.imagetemplate.model.PromptLibraryLoadResult;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ByteArrayResource;

import java.nio.charset.StandardCharsets;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * {@link PromptLibraryLoader} 的加载与降级测试。
 *
 * <p>覆盖三条路径：默认 classpath 大库应加载 4409 条、6 个来源且错误计数为零；JSON 损坏时
 * 不抛异常，而是返回空条目、非零错误计数和含“解析”的可读消息；单行缺字段时只跳过该行，
 * 其余条目保留并把错误计数记为 1。</p>
 *
 * <p>隔离手段：默认用例读取随构建复制的 classpath 资源，异常用例用
 * {@link ByteArrayResource} 提供内存 JSON；不写临时文件、不启动 Spring、不联网。</p>
 */
class PromptLibraryLoaderTest {

    private PromptLibraryLoader loader;

    @BeforeEach
    void setUp() {
        loader = new PromptLibraryLoader(new ObjectMapper());
    }

    @Test
    void loadsAllPromptConsoleEntriesAndSources() {
        PromptLibraryLoadResult result = loader.loadDefault();

        assertThat(result.getEntries()).hasSize(4409);
        assertThat(result.getSources()).hasSize(6);
        assertThat(result.getErrorCount()).isZero();
        assertThat(result.getMessage()).isEmpty();
    }

    @Test
    void reportsMalformedJsonWithoutBreakingProcessAvailability() {
        PromptLibraryLoadResult result =
                loader.load(new ByteArrayResource("{invalid".getBytes(StandardCharsets.UTF_8)));

        assertThat(result.getEntries()).isEmpty();
        assertThat(result.getErrorCount()).isGreaterThan(0);
        assertThat(result.getMessage()).contains("解析");
    }

    @Test
    void skipsInvalidRowsAndReportsDegradedCount() {
        String json = "{\"sources\":[],\"entries\":["
                + "{\"id\":\"ok\",\"sourceId\":\"source\",\"sourceName\":\"Source\","
                + "\"title\":\"有效\",\"category\":\"测试\",\"tags\":[],\"prompt\":\"完整提示词\"},"
                + "{\"id\":\"bad\",\"sourceId\":\"source\",\"sourceName\":\"Source\","
                + "\"title\":\"缺少 Prompt\",\"category\":\"测试\",\"tags\":[]}"
                + "]}";

        PromptLibraryLoadResult result =
                loader.load(new ByteArrayResource(json.getBytes(StandardCharsets.UTF_8)));

        assertThat(result.getEntries()).extracting("id").containsExactly("ok");
        assertThat(result.getErrorCount()).isEqualTo(1);
        assertThat(result.getMessage()).contains("1");
    }
}
