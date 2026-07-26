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
                "libraryAlert", "sourceFilters", "categorySelect", "imageOnlyToggle",
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
                .contains("resetPagination");
    }

    private String read(String path) throws Exception {
        return new String(
                Files.readAllBytes(new ClassPathResource(path).getFile().toPath()),
                StandardCharsets.UTF_8
        );
    }
}
