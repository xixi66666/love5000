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
                .contains("src=\"js/app.js\"")
                .contains("data-scene=\"discover\"")
                .contains("data-scene=\"deconstruct\"")
                .contains("data-scene=\"direct\"")
                .contains("data-scene=\"render\"")
                .contains("class=\"scene-dock\"")
                .contains("class=\"dock-rail-heading\"")
                .contains("id=\"sceneStatus\"")
                .contains("id=\"scenePrevButton\"")
                .contains("id=\"sceneNextButton\"");

        String[] existingIds = {
                "keywordInput", "templateList", "templateCount",
                "libraryAlert", "functionCategoryFilters", "functionCategorySelect",
                "functionSceneFilters",
                "advancedFilters", "sourceFilters", "categorySelect", "imageOnlyToggle",
                "clearFiltersButton", "loadMoreButton", "listStatus",
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
                .contains("<summary>更多筛选</summary>")
                .contains("class=\"deep-woods-video\"")
                .contains("media/background.png")
                .contains("<textarea id=\"jsonTemplate\"")
                .contains("15 个一级功能")
                .contains("class=\"filter-sidebar\"")
                .contains("class=\"results-panel\"")
                .doesNotContain("6 个公开提示词来源");
        assertThat(html.indexOf("id=\"sourceFilters\""))
                .isGreaterThan(html.indexOf("id=\"advancedFilters\""));
        assertThat(html.indexOf("id=\"categorySelect\""))
                .isGreaterThan(html.indexOf("id=\"advancedFilters\""));
    }

    @Test
    void discoverScenePrioritizesTheTemplateSelectionArea() throws Exception {
        String html = read("static/index.html");
        String css = read("static/css/app.css");

        assertThat(html)
                .contains("href=\"css/app.css\"")
                .contains("class=\"discover-summary\"")
                .contains("class=\"primary-action\"");
        assertThat(css)
                .contains("grid-template-columns: minmax(260px, 310px) minmax(0, 1fr);")
                .contains("grid-template-columns: repeat(2, minmax(0, 1fr));")
                .contains("overflow-x: auto;")
                .contains("min-height: 0;");
    }

    @Test
    void discoverSceneUsesMoonNightVisualSystem() throws Exception {
        String css = read("static/css/app.css");
        String normalizedCss = css.replace("\r\n", "\n");

        assertThat(css)
                .contains("--page-bg: #000000;")
                .contains("--ink: #f2f5f8;")
                .contains("--muted: rgba(255, 255, 255, .68);")
                .contains("--gold: rgba(255, 255, 255, .78);")
                .contains("--gold-bright: #ffffff;")
                .contains("--surface: rgba(255, 255, 255, .06);")
                .contains(".cinematic-backdrop")
                .contains(".deep-woods-video")
                .contains("@keyframes aurora-breathe")
                .contains("backdrop-filter: blur(24px) saturate(1.35)")
                .contains(".scene.is-active");
    }

    @Test
    void cinematicStylesAndSceneControllerHaveAccessibilityFallbacks() throws Exception {
        String css = read("static/css/app.css");
        String js = read("static/js/app.js");

        assertThat(css)
                .contains("--gold:")
                .contains("--deep-woods-ink: #000000;")
                .contains("--ink: #f2f5f8;")
                .contains("--page-bg: #000000;")
                .contains("--minimum-target: 44px;")
                .contains(".cinematic-backdrop")
                .contains(".deep-woods-video")
                .contains("@keyframes aurora-breathe")
                .contains("@keyframes aurora-sweep")
                .contains("backdrop-filter: blur(24px) saturate(1.35)")
                .contains(".scene.is-active")
                .contains("--workflow-rail-width: 118px;")
                .contains("grid-template-rows: repeat(4, 56px);")
                .contains("--tiger: #d4a24f;")
                .contains(".load-more")
                .contains("color: var(--tiger);")
                .contains("backdrop-filter: blur(1px) saturate(1.02)")
                .contains(".library-alert")
                .contains(".function-category-toolbar")
                .contains(".function-category-select")
                .contains(".function-filters")
                .contains(".function-scenes")
                .contains("@media (min-width: 1320px)")
                .contains("width: min(1900px, 100%);")
                .contains("height: clamp(600px, 74vh, 860px);")
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
                .contains("clearFilters")
                .contains("syncJsonTemplateToVariables")
                .doesNotContain("elements.variablesInput.disabled = direct;")
                .contains("activeFunctionCategory")
                .contains("activeFunctionScene")
                .contains("functionCategory")
                .contains("functionScene")
                .contains("data-function-category")
                .contains("data-function-scene")
                .contains("state.activeFunctionCategory = '';")
                .contains("state.activeFunctionScene = '';");
        int firstOptionalSourceGuard = js.indexOf("if (elements.sourceFilters)");
        assertThat(firstOptionalSourceGuard).isGreaterThan(-1);
        assertThat(js.lastIndexOf("if (elements.sourceFilters)"))
                .isGreaterThan(firstOptionalSourceGuard);
    }

    private String read(String path) throws Exception {
        return new String(
                Files.readAllBytes(new ClassPathResource(path).getFile().toPath()),
                StandardCharsets.UTF_8
        );
    }
}
