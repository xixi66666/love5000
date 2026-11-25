package com.example.personalagent.service;

import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;

import static org.junit.jupiter.api.Assertions.*;

/** 附件分析跟随顶部栏模型选择的路由规则（不连接任何外部服务）。 */
class LocalDocumentsRoutingTest {

    @Test
    void deepSeekRouteExposesConfiguredModel() {
        assertEquals("deepseek-v4-pro", LocalDocuments.deepSeekModel("deepseek:deepseek-v4-pro"));
        assertEquals("deepseek-flash", LocalDocuments.deepSeekModel("deepseek:deepseek-flash"));
        assertEquals("", LocalDocuments.deepSeekModel("mimo:mimo-v2.6-pro"));
        assertEquals("", LocalDocuments.deepSeekModel("opencode-go:deepseek-v4.1-flash"));
        assertEquals("", LocalDocuments.deepSeekModel(""));
        assertEquals("", LocalDocuments.deepSeekModel(null));
    }

    @Test
    void onlyPlainTextAttachmentsCanGoToOtherProviders() {
        assertTrue(LocalDocuments.textLike("txt"));
        assertTrue(LocalDocuments.textLike("md"));
        assertTrue(LocalDocuments.textLike("csv"));
        assertTrue(LocalDocuments.textLike("json"));
        assertTrue(LocalDocuments.textLike("html"));
        assertFalse(LocalDocuments.textLike("pdf"));
        assertFalse(LocalDocuments.textLike("docx"));
        assertFalse(LocalDocuments.textLike("jpg"));
        assertFalse(LocalDocuments.textLike("xlsx"));
        assertFalse(LocalDocuments.textLike(null));
    }

    @Test
    void unsupportedOriginalReportsUnprocessableEntity() {
        assertEquals(HttpStatus.UNPROCESSABLE_ENTITY, LocalDocuments.unsupportedOriginal().getStatus());
        assertTrue(String.valueOf(LocalDocuments.unsupportedOriginal().getReason()).contains("DeepSeek"));
    }
}
