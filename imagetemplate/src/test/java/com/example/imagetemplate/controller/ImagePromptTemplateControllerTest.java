package com.example.imagetemplate.controller;

import com.example.imagetemplate.service.ImagePromptTemplateAdapter;
import com.example.imagetemplate.service.ImagePromptTemplateService;
import com.example.imagetemplate.service.OpenAiImageGenerationService;
import com.example.imagetemplate.service.PromptLibraryLoader;
import com.example.imagetemplate.service.TemplateFunctionClassifier;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import static org.mockito.Mockito.mock;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * {@link ImagePromptTemplateController} 的 MockMvc 契约测试。
 *
 * <p>服务层使用真实实现装载 classpath 上的 47 条精选模板与 4409 条大库，因此断言的是真实
 * 聚合结果的 HTTP 形状：列表按 48 条分页且只含摘要、meta 总量为 4456、来源 7 个、一级
 * 功能 15 个、功能筛选按 slug 命中、详情返回完整 prompt、{@code size=101} 返回 400 并提示
 * 上限 100。</p>
 *
 * <p>隔离手段：只装配当前 Controller 的 {@code standaloneSetup}，并把
 * {@link OpenAiImageGenerationService} 替换为 Mockito mock；生成接口在测试中不会被调用，
 * 因而不联网、不需要 API Key。</p>
 */
class ImagePromptTemplateControllerTest {

    private static MockMvc mockMvc;

    @BeforeAll
    static void setUp() {
        ObjectMapper objectMapper = new ObjectMapper();
        ImagePromptTemplateService templateService = new ImagePromptTemplateService(
                objectMapper,
                new PromptLibraryLoader(objectMapper),
                new ImagePromptTemplateAdapter(),
                new TemplateFunctionClassifier());
        ImagePromptTemplateController controller = new ImagePromptTemplateController(
                templateService,
                mock(OpenAiImageGenerationService.class),
                objectMapper);
        mockMvc = MockMvcBuilders.standaloneSetup(controller).build();
    }

    @Test
    void listReturnsPagedSummariesWithoutFullPromptPayload() throws Exception {
        mockMvc.perform(get("/api/image-templates")
                        .param("page", "1")
                        .param("size", "48")
                        .param("source", "curated")
                        .param("imageOnly", "true"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.total").value(47))
                .andExpect(jsonPath("$.page").value(1))
                .andExpect(jsonPath("$.size").value(48))
                .andExpect(jsonPath("$.templates[0].promptTemplate").doesNotExist())
                .andExpect(jsonPath("$.templates[0].jsonTemplate").doesNotExist());
    }

    @Test
    void metaReturnsAggregateCountsSourcesAndReadyStatus() throws Exception {
        mockMvc.perform(get("/api/image-templates/meta"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.total").value(4456))
                .andExpect(jsonPath("$.status.status").value("READY"))
                .andExpect(jsonPath("$.sources.length()").value(7))
                .andExpect(jsonPath("$.functionCategories.length()").value(15))
                // 一级功能顺序由分类器目录固定，编程与技术开发固定在第 7 位（索引 6）。
                .andExpect(jsonPath("$.functionCategories[6].slug")
                        .value("programming-development"));
    }

    @Test
    void listFiltersByFunctionAndReturnsFunctionalSummaryFields() throws Exception {
        mockMvc.perform(get("/api/image-templates")
                        .param("functionCategory", "programming-development")
                        .param("functionScene", "debugging"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.total").value(
                        org.hamcrest.Matchers.greaterThan(0)))
                .andExpect(jsonPath("$.templates[0].functionCategory")
                        .value("编程与技术开发"))
                .andExpect(jsonPath("$.templates[0].functionCategorySlug")
                        .value("programming-development"))
                .andExpect(jsonPath("$.templates[0].functionScene")
                        .value("Bug 排查与调试"))
                .andExpect(jsonPath("$.templates[0].functionSceneSlug")
                        .value("debugging"));
    }

    @Test
    void detailReturnsFullTemplatePayload() throws Exception {
        mockMvc.perform(get("/api/image-templates/commerce-product-poster"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.template.promptTemplate").isNotEmpty())
                .andExpect(jsonPath("$.template.jsonTemplate").isMap());
    }

    @Test
    void invalidPageSizeReturnsStableBadRequest() throws Exception {
        mockMvc.perform(get("/api/image-templates").param("size", "101"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value(
                        org.hamcrest.Matchers.containsString("100")));
    }
}
