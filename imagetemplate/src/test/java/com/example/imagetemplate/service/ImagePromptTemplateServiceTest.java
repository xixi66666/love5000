package com.example.imagetemplate.service;

import com.example.imagetemplate.dto.ImageTemplateMetaResponse;
import com.example.imagetemplate.dto.ImageTemplatePageResponse;
import com.example.imagetemplate.dto.ImageTemplateQuery;
import com.example.imagetemplate.dto.PromptRenderRequest;
import com.example.imagetemplate.dto.TemplateFunctionCategoryResponse;
import com.example.imagetemplate.model.ImagePromptTemplate;
import com.example.imagetemplate.model.PromptLibraryEntry;
import com.example.imagetemplate.model.PromptLibraryLoadResult;
import com.example.imagetemplate.model.PromptLibrarySource;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class ImagePromptTemplateServiceTest {

    private ImagePromptTemplateService imagePromptTemplateService;

    @BeforeEach
    void setUp() {
        ObjectMapper objectMapper = new ObjectMapper();
        imagePromptTemplateService = new ImagePromptTemplateService(
                objectMapper,
                new PromptLibraryLoader(objectMapper),
                new ImagePromptTemplateAdapter(),
                new TemplateFunctionClassifier());
    }

    @Test
    void aggregatesCuratedAndSharedLibrariesWithoutDroppingRows() {
        ImageTemplateMetaResponse meta = imagePromptTemplateService.getMeta();

        assertThat(meta.getStatus().getStatus()).isEqualTo("READY");
        assertThat(meta.getStatus().getLoadedCuratedCount()).isEqualTo(47);
        assertThat(meta.getStatus().getLoadedLibraryCount()).isEqualTo(4409);
        assertThat(meta.getTotal()).isEqualTo(4456);
        assertThat(meta.getSources()).hasSize(7);
    }

    @Test
    void aggregateIdsAreUniqueAndCuratedTemplatesRemainFirst() {
        List<ImagePromptTemplate> templates = imagePromptTemplateService.listTemplates(null, null);

        assertThat(templates).hasSize(4456);
        assertThat(templates).extracting("id").doesNotHaveDuplicates();
        assertThat(templates.subList(0, 47)).allMatch(ImagePromptTemplate::isCurated);
    }

    @Test
    void assignsACompleteFunctionClassificationToEveryTemplate() {
        assertThat(imagePromptTemplateService.listTemplates(null, null))
                .hasSize(4456)
                .allSatisfy(template -> {
                    assertThat(template.getFunctionCategory()).isNotBlank();
                    assertThat(template.getFunctionCategorySlug()).isNotBlank();
                    assertThat(template.getFunctionScene()).isNotBlank();
                    assertThat(template.getFunctionSceneSlug()).isNotBlank();
                });
    }

    @Test
    void buildsAnOrderedFunctionalTreeWhoseCountsCoverTheAggregate() {
        List<TemplateFunctionCategoryResponse> categories =
                imagePromptTemplateService.getMeta().getFunctionCategories();

        assertThat(categories).hasSize(15);
        assertThat(categories).extracting("slug")
                .contains("programming-development");
        assertThat(categories.stream().mapToInt(
                TemplateFunctionCategoryResponse::getCount).sum()).isEqualTo(4456);

        TemplateFunctionCategoryResponse programming = categories.stream()
                .filter(category -> "programming-development".equals(category.getSlug()))
                .findFirst()
                .orElseThrow(AssertionError::new);
        assertThat(programming.getCount()).isGreaterThan(0);
        assertThat(programming.getScenes()).isNotEmpty();
        assertThat(programming.getScenes().stream().mapToInt(
                scene -> scene.getCount()).sum()).isEqualTo(programming.getCount());
    }

    @Test
    void listTemplatesLoadsAllCuratedCategories() {
        assertThat(imagePromptTemplateService.listCategories()).extracting("slug")
                .contains("character", "visual-design", "commerce", "editing", "direct-prompt");
    }

    @Test
    void listTemplatesLoadsDirectPromptTemplatesWithEmptyJsonTemplate() {
        List<ImagePromptTemplate> templates =
                imagePromptTemplateService.listTemplates("direct-prompt", null);

        assertThat(templates).hasSize(20);
        assertThat(templates).allSatisfy(template -> {
            assertThat(template.getCategory()).isEqualTo("直接提示词");
            assertThat(template.getCategorySlug()).isEqualTo("direct-prompt");
            assertThat(template.getJsonTemplate()).isEmpty();
            assertThat(template.getPromptTemplate()).contains("生成");
            assertThat(template.getPromptTemplate()).doesNotContain("<");
            assertThat(template.getPromptTemplate().length()).isGreaterThan(80);
            assertThat(template.getSourceUrl()).startsWith("https://github.com/");
            assertThat(template.getTemplateKind()).isEqualTo("DIRECT");
        });
    }

    @Test
    void listTemplatesIncludesCuratedGithubPromptSources() {
        List<ImagePromptTemplate> templates =
                imagePromptTemplateService.listTemplates(null, null);

        assertThat(hasSourceUrlContaining(templates, "YouMind-OpenLab/awesome-gpt-image-2")).isTrue();
        assertThat(hasSourceUrlContaining(templates, "EvoLinkAI/awesome-gpt-image-2-prompts")).isTrue();
        assertThat(hasSourceUrlContaining(templates, "freestylefly/awesome-gpt-image-2")).isTrue();
    }

    @Test
    void listTemplatesIncludesStructuredGithubTemplates() {
        assertThat(imagePromptTemplateService.findById("brand-launch-key-visual").getJsonTemplate()).isNotEmpty();
        assertThat(imagePromptTemplateService.findById("knowledge-card-explainer").getJsonTemplate()).isNotEmpty();
        assertThat(imagePromptTemplateService.findById("mobile-app-store-screenshot").getJsonTemplate()).isNotEmpty();
        assertThat(imagePromptTemplateService.findById("heritage-style-poster").getJsonTemplate()).isNotEmpty();
        assertThat(imagePromptTemplateService.findById("document-report-cover").getJsonTemplate()).isNotEmpty();
        assertThat(imagePromptTemplateService.findById("character-reference-sheet").getJsonTemplate()).isNotEmpty();
    }

    @Test
    void listTemplatesFiltersByCategoryAndKeyword() {
        assertThat(imagePromptTemplateService.listTemplates("character", "头像"))
                .extracting("id")
                .contains("id-photo-headshot", "social-avatar");
    }

    @Test
    void pagesAndFiltersTemplatesUsingSummaryResults() {
        ImageTemplateQuery query = new ImageTemplateQuery();
        query.setPage(1);
        query.setSize(48);
        query.setSource("youmind-awesome-gpt-image-2");
        query.setImageOnly(true);

        ImageTemplatePageResponse page = imagePromptTemplateService.search(query);

        assertThat(page.getTemplates()).hasSizeLessThanOrEqualTo(48);
        assertThat(page.getTotal()).isGreaterThan(0);
        assertThat(page.getTemplates()).allMatch(item ->
                "youmind-awesome-gpt-image-2".equals(item.getSourceId())
                        && item.isImageRelated());
    }

    @Test
    void directTemplateReturnsOriginalPromptAndAppendsDirectorNote() {
        ImageTemplateQuery query = new ImageTemplateQuery();
        query.setSource("prompt123");
        ImagePromptTemplate template =
                imagePromptTemplateService.findById(imagePromptTemplateService.search(query)
                        .getTemplates().get(0).getId());
        PromptRenderRequest request = new PromptRenderRequest();
        request.setExtraInstruction("改成适合图像生成的构图。");

        assertThat(imagePromptTemplateService.renderPrompt(template.getId(), request))
                .startsWith(template.getPromptTemplate())
                .endsWith("用户补充要求：改成适合图像生成的构图。");
    }

    @Test
    void rejectsInvalidPagination() {
        ImageTemplateQuery invalidPage = new ImageTemplateQuery();
        invalidPage.setPage(0);
        ImageTemplateQuery invalidSize = new ImageTemplateQuery();
        invalidSize.setSize(101);

        assertThatThrownBy(() -> imagePromptTemplateService.search(invalidPage))
                .isInstanceOf(ImageTemplateQueryValidationException.class);
        assertThatThrownBy(() -> imagePromptTemplateService.search(invalidSize))
                .isInstanceOf(ImageTemplateQueryValidationException.class);
    }

    @Test
    void reportsDegradedLibraryAndKeepsCuratedTemplates() {
        PromptLibraryLoader degradedLoader = mock(PromptLibraryLoader.class);
        when(degradedLoader.loadDefault()).thenReturn(new PromptLibraryLoadResult(
                Collections.<PromptLibrarySource>emptyList(),
                Collections.<PromptLibraryEntry>emptyList(),
                1,
                "大库资源解析失败"));
        ImagePromptTemplateService degradedService = new ImagePromptTemplateService(
                new ObjectMapper(),
                degradedLoader,
                new ImagePromptTemplateAdapter(),
                new TemplateFunctionClassifier());

        assertThat(degradedService.getMeta().getStatus().getStatus()).isEqualTo("DEGRADED");
        assertThat(degradedService.getMeta().getTotal()).isEqualTo(47);
        assertThat(degradedService.search(new ImageTemplateQuery()).getTemplates()).hasSize(47);
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
        assertThatThrownBy(() -> imagePromptTemplateService.findById("missing"))
                .isInstanceOf(ImagePromptTemplateNotFoundException.class);
    }

    private boolean hasSourceUrlContaining(List<ImagePromptTemplate> templates, String value) {
        for (ImagePromptTemplate template : templates) {
            if (template.getSourceUrl() != null && template.getSourceUrl().contains(value)) {
                return true;
            }
        }
        return false;
    }
}
