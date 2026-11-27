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

/**
 * {@link ImagePromptTemplateService} 的聚合、筛选与渲染测试。
 *
 * <p>核心断言：47 条精选加 4409 条大库必须得到 4456 条且 ID 全局唯一、精选永远排在最前；
 * 每条模板都被分类器补全一级功能与二级场景；功能树一级计数之和必须闭合到 4456，编程类的
 * 二级场景计数之和等于该一级计数；分类、直接提示词、GitHub 来源、关键词、来源与
 * {@code imageOnly} 过滤行为正确；非法分页参数抛校验异常；直接提示词以原文开头并追加导演
 * 备注或用户变量；结构化模板合并变量后仍保留任务描述；模板不存在时抛 not found。</p>
 *
 * <p>隔离手段：正常用例使用真实 loader 读取 classpath 数据；{@code DEGRADED} 用例用
 * Mockito 替换 {@link PromptLibraryLoader}，让大库返回错误计数，验证只保留 47 条精选、
 * 状态降级但仍可查询。全程不启动 Spring、不联网。</p>
 */
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

        // 直接提示词固定 20 条，同时充当中文文案与无占位符约束的样例集。
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
    void filtersByFunctionCategoryAndSceneWhileKeepingLegacyFilters() {
        ImageTemplateQuery programming = new ImageTemplateQuery();
        programming.setFunctionCategory("programming-development");
        ImageTemplatePageResponse programmingPage =
                imagePromptTemplateService.search(programming);

        assertThat(programmingPage.getTotal()).isGreaterThan(0);
        assertThat(programmingPage.getTemplates()).allSatisfy(item -> {
            assertThat(item.getFunctionCategorySlug())
                    .isEqualTo("programming-development");
            assertThat(item.getFunctionSceneSlug()).isNotBlank();
        });

        ImageTemplateQuery debugging = new ImageTemplateQuery();
        debugging.setFunctionCategory("programming-development");
        debugging.setFunctionScene("debugging");
        ImageTemplatePageResponse debuggingPage =
                imagePromptTemplateService.search(debugging);

        assertThat(debuggingPage.getTotal()).isGreaterThan(0);
        assertThat(debuggingPage.getTemplates()).allSatisfy(item -> {
            assertThat(item.getFunctionCategorySlug())
                    .isEqualTo("programming-development");
            assertThat(item.getFunctionSceneSlug()).isEqualTo("debugging");
        });

        ImageTemplateQuery sourceOnly = new ImageTemplateQuery();
        sourceOnly.setSource("prompt123");
        assertThat(imagePromptTemplateService.search(sourceOnly).getTemplates())
                .allMatch(item -> "prompt123".equals(item.getSourceId()));
    }

    @Test
    void sceneOnlyQueryMatchesAcrossCategories() {
        ImageTemplateQuery query = new ImageTemplateQuery();
        query.setFunctionScene("debugging");

        ImageTemplatePageResponse page = imagePromptTemplateService.search(query);

        assertThat(page.getTotal()).isGreaterThan(0);
        assertThat(page.getTemplates())
                .allMatch(item -> "debugging".equals(item.getFunctionSceneSlug()));
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
    void directTemplateAppendsManuallyEnteredVariables() {
        ImageTemplateQuery query = new ImageTemplateQuery();
        query.setSource("prompt123");
        ImagePromptTemplate template =
                imagePromptTemplateService.findById(imagePromptTemplateService.search(query)
                        .getTemplates().get(0).getId());
        PromptRenderRequest request = new PromptRenderRequest();
        Map<String, Object> variables = new LinkedHashMap<String, Object>();
        variables.put("主体", "月光下的白色小屋");
        variables.put("画幅", "竖版 4:5");
        request.setVariables(variables);

        assertThat(imagePromptTemplateService.renderPrompt(template.getId(), request))
                .contains("用户变量：")
                .contains("主体: 月光下的白色小屋")
                .contains("画幅: 竖版 4:5");
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
        // 用 mock 制造大库加载失败，确认降级时精选库仍可服务且状态为 DEGRADED。
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

    /**
     * 判断是否存在来源链接包含指定片段的模板。
     *
     * <p>精选库允许 {@code sourceUrl} 为空，因此先判空再匹配，避免数据缺口让用例抛空指针。</p>
     */
    private boolean hasSourceUrlContaining(List<ImagePromptTemplate> templates, String value) {
        for (ImagePromptTemplate template : templates) {
            if (template.getSourceUrl() != null && template.getSourceUrl().contains(value)) {
                return true;
            }
        }
        return false;
    }
}
