package com.example.website.prompt.library;

import com.example.website.prompt.library.controller.PromptLibraryController;
import com.example.website.prompt.library.dto.PromptCreateResponse;
import com.example.website.prompt.library.dto.PromptDetailResponse;
import com.example.website.prompt.library.dto.PromptListResponse;
import com.example.website.prompt.library.dto.PromptMetaResponse;
import com.example.website.prompt.library.service.PromptLibraryService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.util.Arrays;
import java.util.Collections;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class PromptLibraryControllerTest {

    private final PromptLibraryService service = mock(PromptLibraryService.class);
    private MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        mockMvc = MockMvcBuilders
                .standaloneSetup(new PromptLibraryController(service))
                .build();
    }

    @Test
    void metaReturnsGroupsAndSources() throws Exception {
        PromptMetaResponse meta = new PromptMetaResponse();
        meta.setTotal(3L);
        PromptMetaResponse.GroupSummary group = new PromptMetaResponse.GroupSummary();
        group.setSlug("development-technology");
        group.setName("开发与技术");
        group.setCount(2L);
        group.setCategories(Collections.singletonList(new PromptMetaResponse.CategorySummary("技术与编程", 2L)));
        meta.setGroups(Collections.singletonList(group));
        PromptMetaResponse.SourceSummary source = new PromptMetaResponse.SourceSummary();
        source.setId("awesome");
        source.setName("Awesome");
        source.setStatus("imported");
        source.setCount(3L);
        meta.setSources(Collections.singletonList(source));
        when(service.meta()).thenReturn(meta);

        mockMvc.perform(get("/api/prompts/meta"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.total").value(3))
                .andExpect(jsonPath("$.groups[0].slug").value("development-technology"))
                .andExpect(jsonPath("$.groups[0].categories[0].name").value("技术与编程"))
                .andExpect(jsonPath("$.sources[0].id").value("awesome"));
    }

    @Test
    void listReturnsPagedEntries() throws Exception {
        PromptListResponse response = new PromptListResponse();
        response.setTotal(1L);
        response.setPage(1);
        response.setSize(48);
        PromptListResponse.EntrySummary entry = new PromptListResponse.EntrySummary();
        entry.setId(1L);
        entry.setTitle("小红书爆款");
        entry.setCategory("小红书");
        entry.setGroupSlug("writing-content");
        entry.setGroupName("写作与内容");
        entry.setSourceName("Prompt123");
        entry.setTags(Arrays.asList("小红书", "爆款"));
        entry.setLicense("授权");
        entry.setStatus("imported");
        entry.setPreview("preview...");
        response.setEntries(Collections.singletonList(entry));
        when(service.search(any())).thenReturn(response);

        mockMvc.perform(get("/api/prompts")
                        .param("keyword", "爆款")
                        .param("group", "writing-content")
                        .param("page", "1")
                        .param("size", "48"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.total").value(1))
                .andExpect(jsonPath("$.entries[0].title").value("小红书爆款"))
                .andExpect(jsonPath("$.entries[0].tags[1]").value("爆款"))
                .andExpect(jsonPath("$.entries[0].preview").value("preview..."));
    }

    @Test
    void detailReturnsEntry() throws Exception {
        PromptDetailResponse response = new PromptDetailResponse();
        PromptDetailResponse.EntryDetail detail = new PromptDetailResponse.EntryDetail();
        detail.setId(1L);
        detail.setTitle("小红书爆款");
        detail.setCategory("小红书");
        detail.setGroupSlug("writing-content");
        detail.setSourceName("Prompt123");
        detail.setSourceUrl("https://example.com");
        detail.setPrompt("完整正文");
        detail.setTags(Collections.singletonList("爆款"));
        response.setEntry(detail);
        when(service.detail(1L)).thenReturn(response);

        mockMvc.perform(get("/api/prompts/1"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.entry.title").value("小红书爆款"))
                .andExpect(jsonPath("$.entry.prompt").value("完整正文"));
    }

    @Test
    void detailNotFoundReturns404() throws Exception {
        when(service.detail(99L)).thenReturn(null);

        mockMvc.perform(get("/api/prompts/99"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value("提示词不存在"));
    }

    @Test
    void createReturnsSavedEntry() throws Exception {
        PromptCreateResponse response = new PromptCreateResponse();
        PromptDetailResponse.EntryDetail detail = new PromptDetailResponse.EntryDetail();
        detail.setId(9L);
        detail.setTitle("新提示词");
        detail.setCategory("小红书");
        detail.setGroupSlug("writing-content");
        detail.setGroupName("写作与内容");
        detail.setSourceName("手动添加");
        detail.setPrompt("正文");
        detail.setTags(Collections.singletonList("标签A"));
        response.setEntry(detail);
        when(service.create(any())).thenReturn(response);

        mockMvc.perform(post("/api/prompts")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"title\":\"新提示词\",\"category\":\"小红书\",\"prompt\":\"正文\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.entry.id").value(9))
                .andExpect(jsonPath("$.entry.title").value("新提示词"))
                .andExpect(jsonPath("$.entry.sourceName").value("手动添加"))
                .andExpect(jsonPath("$.entry.prompt").value("正文"));
    }

    @Test
    void createValidationErrorReturns400() throws Exception {
        when(service.create(any())).thenThrow(new IllegalArgumentException("标题不能为空"));

        mockMvc.perform(post("/api/prompts")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"title\":\"\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value("标题不能为空"));
    }
}