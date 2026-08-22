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
