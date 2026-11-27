package com.example.website.prompt.controller;

import com.example.website.prompt.model.PromptSourceSnapshot;
import com.example.website.prompt.model.PromptVariant;
import com.example.website.prompt.service.PromptComposeService;
import com.example.website.prompt.service.PromptSourceFetchService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.time.OffsetDateTime;
import java.util.Arrays;
import java.util.Collections;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * 提示词控制台接口 {@link PromptConsoleController} 的 MVC 切片测试。
 *
 * <p>用 {@code @WebMvcTest} 只装配控制器，{@link PromptSourceFetchService} 与
 * {@link PromptComposeService} 由 {@code @MockBean} 替换，固定三条响应约定：
 * 来源列表与刷新都包在 {@code success=true} 里，把快照放进 {@code sources}；
 * 组合接口把服务返回的变体放进 {@code results}，类型字段供前端分栏展示；
 * 服务抛 {@link IllegalArgumentException}（场景只有空白）时仍然返回 HTTP 200，
 * 用 {@code success=false} + {@code message} 表达业务错误——前端只看 {@code success}，
 * 校验失败不该表现为 5xx。</p>
 *
 * <p>隔离：切片测试不加载数据库和 Druid，不发起真实抓取，也不真正拼装提示词。</p>
 */
@WebMvcTest(PromptConsoleController.class)
class PromptConsoleControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockBean
    private PromptSourceFetchService fetchService;

    @MockBean
    private PromptComposeService composeService;

    @Test
    void listSourcesReturnsSuccessWrapper() throws Exception {
        when(fetchService.listSnapshots()).thenReturn(Collections.singletonList(new PromptSourceSnapshot(
                "prompt123",
                "Prompt123",
                "https://prompt123.cn/?utm_source=novatools.cn",
                "website",
                Arrays.asList("提示词网站"),
                "fallback",
                "提示词来源摘要",
                OffsetDateTime.now(),
                "Using built-in source summary.")));

        mockMvc.perform(get("/api/prompt-sources"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.sources[0].sourceId").value("prompt123"));
    }

    @Test
    void refreshSourcesReturnsSuccessWrapper() throws Exception {
        when(fetchService.refresh(Arrays.asList("prompt123"))).thenReturn(Collections.singletonList(new PromptSourceSnapshot(
                "prompt123",
                "Prompt123",
                "https://prompt123.cn/?utm_source=novatools.cn",
                "website",
                Arrays.asList("提示词网站"),
                "fallback",
                "提示词来源摘要",
                OffsetDateTime.now(),
                "Using built-in source summary.")));

        mockMvc.perform(post("/api/prompt-sources/refresh")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"sourceIds\":[\"prompt123\"]}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.sources[0].sourceId").value("prompt123"));
    }

    @Test
    void composeReturnsPromptVariants() throws Exception {
        when(composeService.compose(any())).thenReturn(Collections.singletonList(new PromptVariant(
                "image",
                "图片生成版",
                "生成一张雨夜城市街巷图片",
                Arrays.asList("prompt123"),
                Arrays.asList("主体", "场景"))));

        mockMvc.perform(post("/api/prompts/compose")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"scene\":\"雨夜城市街巷\",\"purpose\":\"image\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.results[0].type").value("image"));
    }

    @Test
    void composeBlankSceneReturnsErrorWrapper() throws Exception {
        when(composeService.compose(any())).thenThrow(new IllegalArgumentException("场景不能为空"));

        // 业务校验失败不改变 HTTP 状态码：前端统一按 success 字段判断。
        mockMvc.perform(post("/api/prompts/compose")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"scene\":\" \"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value("场景不能为空"));
    }
}
