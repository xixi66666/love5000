package com.example.imagetemplate.service;

import com.example.imagetemplate.model.PromptLibraryLoadResult;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ByteArrayResource;

import java.nio.charset.StandardCharsets;

import static org.assertj.core.api.Assertions.assertThat;

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
