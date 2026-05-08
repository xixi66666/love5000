package com.example.imagetemplate.service;

import com.example.imagetemplate.dto.PromptRenderRequest;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.LinkedHashMap;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class ImagePromptTemplateServiceTest {

    private ImagePromptTemplateService imagePromptTemplateService;

    @BeforeEach
    void setUp() {
        imagePromptTemplateService = new ImagePromptTemplateService(new ObjectMapper());
    }

    @Test
    void listTemplatesLoadsAllCuratedTemplates() {
        assertThat(imagePromptTemplateService.listTemplates(null, null)).hasSize(21);
        assertThat(imagePromptTemplateService.listCategories()).extracting("slug")
                .contains("character", "visual-design", "commerce", "editing");
    }

    @Test
    void listTemplatesFiltersByCategoryAndKeyword() {
        assertThat(imagePromptTemplateService.listTemplates("character", "头像"))
                .extracting("id")
                .contains("id-photo-headshot", "social-avatar");
    }

    @Test
    void renderPromptMergesUserVariablesIntoJsonTemplate() {
        PromptRenderRequest request = new PromptRenderRequest();
        Map<String, Object> variables = new LinkedHashMap<String, Object>();
        variables.put("product_name", "月光玻璃杯");
        variables.put("campaign_text", "新品首发");
        request.setVariables(variables);
        request.setExtraInstruction("竖版 4:5，背景更干净。");

        String prompt = imagePromptTemplateService.renderPrompt("commerce-product-poster", request);

        assertThat(prompt).contains("图像生成任务：商品海报 / 电商图生成");
        assertThat(prompt).contains("product_name: 月光玻璃杯");
        assertThat(prompt).contains("campaign_text: 新品首发");
        assertThat(prompt).contains("竖版 4:5");
        assertThat(prompt).contains("prompt 字段");
    }

    @Test
    void findByIdThrowsWhenTemplateIsMissing() {
        assertThatThrownBy(new org.assertj.core.api.ThrowableAssert.ThrowingCallable() {
            @Override
            public void call() {
                imagePromptTemplateService.findById("missing");
            }
        }).isInstanceOf(ImagePromptTemplateNotFoundException.class);
    }
}
