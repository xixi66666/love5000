package com.example.website;

import org.junit.jupiter.api.Test;
import org.yaml.snakeyaml.Yaml;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 首页静态资源契约测试。
 *
 * <p>直接读取 classpath 下的 {@code static/index.html}、{@code static/css/style.css}、
 * {@code static/js/script.js} 与 {@code application.yml}，断言四段场景视频、液态玻璃 Dock、
 * 01 的 9 个入口、03 Deep Woods 只保留个人资料库、02/04 空目录隐藏、顶栏只剩账户操作，
 * 以及每张卡片挂的 {@code data-health-url} / {@code data-start-url}。这些字符串是前后端约定，
 * 页面改动漏掉入口时这里先失败，不必等人工点页面。</p>
 *
 * <p>跨文件的一致性只在这一处校验：Dock 卡片数 = 健康清单条数 - 合并的本机服务 + 本地页面入口，
 * 清单来自 SnakeYAML 解析后的 {@code website.service-health.services}，避免在测试里硬编码 11。
 * 隔离方式：不起 Spring 上下文、不发 HTTP 请求、不连 MySQL，全部是字符串匹配。</p>
 */
class HomepageStaticAssetsTest {

    @Test
    void homepageContainsCinematicScenesAndEveryServiceEntry() throws IOException {
        String html = readResource("/static/index.html");

        // 四段场景视频是写死在页面里的外部 URL，文件名本身就是契约。
        assertTrue(html.contains("hf_20260702_081127_0992a171-d3c6-4978-8213-0ec5df8b6d63.mp4"));
        assertTrue(html.contains("hf_20260702_092026_dd05b805-ea0f-40b2-8c52-332b88502592.mp4"));
        assertTrue(html.contains("hf_20260702_081042_df7202bf-bd80-4b2b-bbc6-1f09ba2870e9.mp4"));
        assertTrue(html.contains("hf_20260702_080959_4cac5234-3573-464e-a5b7-76b94b8a7d61.mp4"));
        assertTrue(html.contains("data-scene-index=\"2\""));
        assertFalse(html.contains("class=\"mobile-menu\""));
        assertTrue(html.contains("liquid-glass"));

        assertTrue(html.contains("data-health-url=\"http://localhost:8081/login.html\""));
        assertTrue(html.contains("data-health-url=\"http://localhost:8082/index.html\""));
        assertTrue(html.contains("data-health-url=\"/prompt-console/index.html\""));
        assertTrue(html.contains("data-health-url=\"http://127.0.0.1:5174/api/health\""));
        assertTrue(html.contains("data-health-url=\"http://127.0.0.1:5175/api/health\""));
        assertTrue(html.contains("data-health-url=\"http://127.0.0.1:5176/api/health\""));
        assertTrue(html.contains("data-health-url=\"http://127.0.0.1:5177/api/health\""));
        assertTrue(html.contains("data-health-url=\"http://127.0.0.1:5178/api/health\""));
        assertTrue(html.contains("data-health-url=\"http://127.0.0.1:5179/api/health\""));
        assertTrue(html.contains("data-start-url=\"/api/services/personal-agent/start\""));
        assertTrue(html.contains("data-start-url=\"/api/services/lottery/start\""));
        assertTrue(html.contains("data-app-url=\"http://127.0.0.1:5179/\""));
        assertTrue(html.contains("data-health-url=\"/local-services/index.html\""));
        // 模型与视频管理页只能有一处链接，避免 Dock 里出现重复卡片。
        assertEquals(1, html.split("href=\"local-services/index.html", -1).length - 1);
        assertTrue(html.contains("data-auth-required=\"true\""));
    }

    /**
     * 首页 Dock 中不参与 service-health 聚合探测的本地页面入口。
     * 当前为 Prompt Console 和模型与视频管理页，由 website 自身提供。
     * 新增此类入口时要同步 +1，否则下面的断言会失败。
     */
    private static final int LOCAL_ONLY_ENTRIES = 2;
    /** 首页合并为一个「模型与视频」入口的本机服务数量（Strata、AIMedia、H3）；各自健康探测仍保留。 */
    private static final int GROUPED_LOCAL_SERVICES = 3;

    @Test
    void homepageDockShowsEveryServiceFromTheHealthList() throws IOException {
        String html = readResource("/static/index.html");
        int homepageCards = html.split("class=\"service-card\"", -1).length - 1;

        Map<?, ?> root = (Map<?, ?>) new Yaml().load(readResource("/application.yml"));
        Map<?, ?> website = (Map<?, ?>) root.get("website");
        Map<?, ?> serviceHealth = (Map<?, ?>) website.get("service-health");
        List<?> services = (List<?>) serviceHealth.get("services");

        assertEquals(services.size() - GROUPED_LOCAL_SERVICES + LOCAL_ONLY_ENTRIES, homepageCards,
                "首页 Dock 卡片数 = service-health 清单 - 合并的本机服务 + 本地页面入口");

        assertEquals("health", ((Map<?, ?>) services.get(services.size() - 1)).get("name"),
                "新服务追加在健康清单末尾，不改变原服务顺序");
    }

    @Test
    void personalAgentStaysInDeepWoodsAndGoldenHourKeepsNineEntries() throws IOException {
        String html = readResource("/static/index.html");
        String goldenHour = dock(html, "service-dock");
        String deepWoods = dock(html, "deep-woods-service-dock");

        assertEquals(9, countCards(goldenHour));
        assertFalse(goldenHour.contains("personal-agent"));
        assertTrue(goldenHour.contains("data-health-service=\"lottery\""));
        assertTrue(goldenHour.contains("LOTTERY DESK · 5179"));
        assertEquals(2, countCards(deepWoods));
        assertTrue(deepWoods.contains("data-start-url=\"/api/services/health/start\""));
        assertTrue(deepWoods.contains("data-app-url=\"http://127.0.0.1:5178/\""));
        assertTrue(deepWoods.contains("OBSIDIAN + QUARTZ · 5178"));
        assertEquals(0, countCards(dock(html, "still-water-service-dock")));
        assertEquals(0, countCards(dock(html, "quiet-dawn-service-dock")));
        // 其他场景的服务不得重复塞进 03 Deep Woods。
        assertFalse(deepWoods.contains("5174"));
        assertFalse(deepWoods.contains("5177"));
        assertFalse(deepWoods.contains("5179"));
    }

    @Test
    void homepageStylesAndScriptsExposeTheRequiredInteractions() throws IOException {
        String css = readResource("/static/css/style.css");
        String javascript = readResource("/static/js/script.js");

        assertTrue(css.contains(".liquid-glass::before"));
        assertTrue(css.contains("@keyframes ken-burns"));
        assertTrue(css.contains(".scene-deep-woods"));
        assertTrue(css.contains(".scene-video--loop"));
        assertTrue(css.contains("@media (prefers-reduced-motion: reduce)"));

        assertTrue(javascript.contains("function setupVideoSwitcher()"));
        assertFalse(javascript.contains("function setupMobileMenu()"));
        assertTrue(javascript.contains("function setupAuth()"));
        assertTrue(javascript.contains("function setupServiceHealth()"));
        assertTrue(javascript.contains("transitionLocked"));
        // 场景视频循环必须走交叉淡化补层，不能退回原生 loop 的硬切
        assertTrue(javascript.contains("createLoopLayer"));
        assertTrue(javascript.contains("handoffLoop"));
    }

    @Test
    void desktopHeaderOnlyContainsAuthenticationActions() throws IOException {
        String html = readResource("/static/index.html");
        int navigationStart = html.indexOf("<nav class=\"desktop-navigation");
        int navigationEnd = html.indexOf("</nav>", navigationStart);
        String desktopNavigation = html.substring(navigationStart, navigationEnd);

        assertTrue(desktopNavigation.contains("auth-login-button"));
        assertTrue(desktopNavigation.contains("auth-register-button"));
        assertTrue(desktopNavigation.contains("auth-logout-button"));
        // 顶栏不允许任何链接式入口，服务入口只出现在底部 Dock。
        assertFalse(desktopNavigation.contains("<a "));
        assertEquals(3, desktopNavigation.split("<button", -1).length - 1);
    }

    /**
     * 截取指定 id 的 section 内容，作为该场景的服务 Dock。
     *
     * <p>以最近的 {@code </section>} 作为结束边界。找不到 id 时先断言失败，
     * 避免 substring 抛出的越界异常掩盖「入口被删」这个真实原因。</p>
     */
    private String dock(String html, String id) {
        int start = html.indexOf("id=\"" + id + "\"");
        assertTrue(start >= 0, "Missing service dock: " + id);
        int end = html.indexOf("</section>", start);
        assertTrue(end > start);
        return html.substring(start, end);
    }

    /** 统计片段中 {@code service-card} 的数量；split 保留空串，避免首尾卡片被漏算。 */
    private int countCards(String html) {
        return html.split("class=\"service-card\"", -1).length - 1;
    }

    /**
     * 按 UTF-8 读取 classpath 资源。
     *
     * <p>不走 Spring 的 ResourceLoader，这样不起上下文也能跑；资源缺失时先断言再读，
     * 失败信息直接给出路径。读取后必须关闭输入流，解码固定 UTF-8 以免依赖平台默认编码。</p>
     */
    private String readResource(String path) throws IOException {
        InputStream input = HomepageStaticAssetsTest.class.getResourceAsStream(path);
        assertTrue(input != null, "Missing classpath resource: " + path);
        try {
            ByteArrayOutputStream output = new ByteArrayOutputStream();
            byte[] buffer = new byte[4096];
            int bytesRead;
            while ((bytesRead = input.read(buffer)) != -1) {
                output.write(buffer, 0, bytesRead);
            }
            return new String(output.toByteArray(), StandardCharsets.UTF_8);
        } finally {
            input.close();
        }
    }
}
