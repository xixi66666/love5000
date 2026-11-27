package com.example.imagetemplate;

import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 图片模板工作台静态资源的契约测试。
 *
 * <p>被校验的是打包进 classpath 的 {@code static/index.html}、{@code static/css/app.css}、
 * {@code static/js/app.js} 以及 {@code static/vendor/} 下的 GSAP 资源，而不是运行中的服务：
 * 读取文件文本后断言四场景（discover、deconstruct、direct、render）骨架、场景 Dock、
 * 灵感大厅业务控件 id、月夜配色变量、筛选面板层级和无障碍降级仍然存在。</p>
 *
 * <p>断言锁定的是前端与后端共同依赖的契约：来源和原始分类必须放在“更多筛选”折叠面板内，
 * 场景切换按钮与状态文案的 id 不能被删除，GSAP 必须保持 3.13.0 本地版本。测试只在测试
 * 阶段读取解包后的 classpath 目录，不启动 Spring 上下文、不打开浏览器、不访问网络。</p>
 */
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
                "referenceImageInput", "imageSizeSelect",
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
                .contains("class=\"hero-visual-frame\"")
                .contains("class=\"process-accordion\"")
                .contains("id=\"directionIndex\"")
                .contains("vendor/gsap-3.13.0.min.js")
                .contains("vendor/ScrollTrigger-3.13.0.min.js")
                .doesNotContain("6 个公开提示词来源");
        // 来源与原始分类属于“更多筛选”的二级内容，必须出现在折叠面板之后而不是常驻工具栏。
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
                .contains("grid-auto-flow: dense;")
                .contains("max-width: 1120px;")
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
                .contains("initEditorialMotion")
                .contains("animateTemplateCards")
                .contains("showDirectionSlide")
                .doesNotContain("elements.variablesInput.disabled = direct;")
                .contains("activeFunctionCategory")
                .contains("activeFunctionScene")
                .contains("functionCategory")
                .contains("functionScene")
                .contains("data-function-category")
                .contains("data-function-scene")
                .contains("state.activeFunctionCategory = '';")
                .contains("state.activeFunctionScene = '';");
        assertThat(read("static/vendor/gsap-3.13.0.min.js"))
                .contains("Jt.version=Qt.version=ze.version=\"3.13.0\"");
        assertThat(read("static/vendor/ScrollTrigger-3.13.0.min.js"))
                .contains("ScrollTrigger");
        int firstOptionalSourceGuard = js.indexOf("if (elements.sourceFilters)");
        assertThat(firstOptionalSourceGuard).isGreaterThan(-1);
        assertThat(js.lastIndexOf("if (elements.sourceFilters)"))
                .isGreaterThan(firstOptionalSourceGuard);
    }

    /**
     * 以 UTF-8 读取 classpath 静态资源。
     *
     * <p>通过 {@link ClassPathResource#getFile()} 定位，因此要求资源以解包目录
     * （{@code target/test-classes}）存在；打成 jar 后该方法不可用，此处仅服务于测试阶段。</p>
     */
    private String read(String path) throws Exception {
        return new String(
                Files.readAllBytes(new ClassPathResource(path).getFile().toPath()),
                StandardCharsets.UTF_8
        );
    }
}
