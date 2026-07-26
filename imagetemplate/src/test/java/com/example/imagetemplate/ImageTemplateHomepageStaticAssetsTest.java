package com.example.imagetemplate;

import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

import static org.assertj.core.api.Assertions.assertThat;

class ImageTemplateHomepageStaticAssetsTest {

    @Test
    void homepageDefinesFourScenesDockAndExistingBusinessControls() throws Exception {
        String html = read("static/index.html");

        assertThat(html)
                .contains("rel=\"icon\"")
                .contains("data-scene=\"discover\"")
                .contains("data-scene=\"deconstruct\"")
                .contains("data-scene=\"direct\"")
                .contains("data-scene=\"render\"")
                .contains("class=\"scene-dock\"")
                .contains("id=\"sceneStatus\"")
                .contains("id=\"scenePrevButton\"")
                .contains("id=\"sceneNextButton\"");

        String[] existingIds = {
                "keywordInput", "templateList", "templateCount",
                "libraryAlert", "functionCategoryFilters", "functionCategorySelect",
                "functionSceneFilters",
                "advancedFilters", "sourceFilters", "categorySelect", "imageOnlyToggle",
                "loadMoreButton", "listStatus",
                "detailCategory", "detailTitle", "detailSummary", "jsonTemplate",
                "promptTemplate", "variablesInput", "extraInstructionInput",
                "renderedPrompt", "renderPromptButton", "copyPromptButton",
                "openAiApiKeyInput", "referenceImageInput", "imageSizeSelect",
                "generateImageButton", "generatedImage", "downloadImageButton"
        };
        for (String id : existingIds) {
            assertThat(html).contains("id=\"" + id + "\"");
        }
        assertThat(html)
                .contains("<details id=\"advancedFilters\"")
                .contains("<summary>高级筛选</summary>")
                .contains("15 个一级功能")
                .contains("查看数据出处")
                .doesNotContain("6 个公开提示词来源");
        assertThat(html.indexOf("id=\"sourceFilters\""))
                .isGreaterThan(html.indexOf("id=\"advancedFilters\""));
        assertThat(html.indexOf("id=\"categorySelect\""))
                .isGreaterThan(html.indexOf("id=\"advancedFilters\""));
    }

    @Test
    void cinematicStylesAndSceneControllerHaveAccessibilityFallbacks() throws Exception {
        String css = read("static/css/app.css");
        String js = read("static/js/app.js");

        assertThat(css)
                .contains("--gold:")
                .contains("--minimum-target: 44px;")
                .contains(".cinematic-backdrop")
                .contains(".scene.is-active")
                .contains(".library-alert")
                .contains(".function-category-toolbar")
                .contains(".function-category-select")
                .contains(".function-filters")
                .contains(".function-scenes")
                .contains("grid-template-columns: repeat(auto-fit, minmax(96px, 1fr));")
                .contains("@media (min-width: 1320px)")
                .contains(".advanced-filters")
                .contains(".source-filters")
                .contains(".template-badge")
                .contains(".load-more")
                .contains("@media (prefers-reduced-motion: reduce)");
        assertThat(js)
                .contains("activeScene")
                .contains("setActiveScene")
                .contains("aria-selected")
                .contains("scenePrevButton")
                .contains("sceneNextButton")
                .contains("SEARCH_DEBOUNCE_MS = 300")
                .contains("loadMeta")
                .contains("loadTemplatePage")
                .contains("loadTemplateDetail")
                .contains("resetPagination")
                .contains("functionCategories")
                .contains("functionCategorySelect")
                .contains("selectFunctionCategory")
                .contains("activeFunctionCategory")
                .contains("activeFunctionScene")
                .contains("functionCategory")
                .contains("functionScene")
                .contains("data-function-category")
                .contains("data-function-scene")
                .contains("state.activeFunctionCategory = '';")
                .contains("state.activeFunctionScene = '';");
    }

    private String read(String path) throws Exception {
        return new String(
                Files.readAllBytes(new ClassPathResource(path).getFile().toPath()),
                StandardCharsets.UTF_8
        );
    }
}
