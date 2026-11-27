package com.example.personalagent.service;

import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;

import static org.junit.jupiter.api.Assertions.*;

/**
 * {@link LocalDocuments} 依据顶部栏模型选择做路由的规则测试。
 *
 * <p>覆盖分支：{@code deepseek:} 前缀解析出型号、其他提供方与空值返回空串、文本类后缀
 * 白名单（含 {@code null}），以及「无法解析原件」异常的 422 状态与提示文案。</p>
 *
 * <p>隔离手段：只断言静态纯函数与异常构造，不实例化服务、不读 Vault、不连接任何外部
 * 服务或模型。</p>
 */
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
