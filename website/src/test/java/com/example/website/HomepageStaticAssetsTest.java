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

class HomepageStaticAssetsTest {

    @Test
    void homepageContainsCinematicScenesAndEveryServiceEntry() throws IOException {
        String html = readResource("/static/index.html");

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
        assertTrue(html.contains("data-start-url=\"/api/services/personal-agent/start\""));
        assertTrue(html.contains("data-health-url=\"/local-services/index.html\""));
        assertEquals(1, html.split("href=\"local-services/index.html", -1).length - 1);
        assertTrue(html.contains("data-auth-required=\"true\""));
    }

    /**
     * 首页 Dock 中不参与 service-health 聚合探测的本地页面入口。
     * 当前为 Prompt Console 和模型与视频管理页，由 website 自身提供。
     * 新增此类入口时要同步 +1，否则下面的断言会失败。
     */
    private static final int LOCAL_ONLY_ENTRIES = 2;
    // Strata、AIMedia、H3 的健康检测保留，首页合并到模型与视频管理页入口。
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

        assertEquals("personal-agent", ((Map<?, ?>) services.get(services.size() - 1)).get("name"),
                "新服务追加在健康清单末尾，不改变原服务顺序");
    }

    @Test
    void personalAgentOnlyAppearsInDeepWoodsAndGoldenHourKeepsEightEntries() throws IOException {
        String html = readResource("/static/index.html");
        String goldenHour = dock(html, "service-dock");
        String deepWoods = dock(html, "deep-woods-service-dock");

        assertEquals(8, countCards(goldenHour));
        assertFalse(goldenHour.contains("personal-agent"));
        assertEquals(1, countCards(deepWoods));
        assertTrue(deepWoods.contains("data-app-url=\"http://127.0.0.1:5178/\""));
        assertTrue(deepWoods.contains("PERSONAL AGENT · 5178"));
        assertEquals(0, countCards(dock(html, "still-water-service-dock")));
        assertEquals(0, countCards(dock(html, "quiet-dawn-service-dock")));
        assertFalse(deepWoods.contains("5174"));
        assertFalse(deepWoods.contains("5177"));
    }

    @Test
    void homepageStylesAndScriptsExposeTheRequiredInteractions() throws IOException {
        String css = readResource("/static/css/style.css");
        String javascript = readResource("/static/js/script.js");

        assertTrue(css.contains(".liquid-glass::before"));
        assertTrue(css.contains("@keyframes train-bob"));
        assertTrue(css.contains(".scene-deep-woods"));
        assertTrue(css.contains("@media (prefers-reduced-motion: reduce)"));

        assertTrue(javascript.contains("function setupVideoSwitcher()"));
        assertFalse(javascript.contains("function setupMobileMenu()"));
        assertTrue(javascript.contains("function setupAuth()"));
        assertTrue(javascript.contains("function setupServiceHealth()"));
        assertTrue(javascript.contains("transitionLocked"));
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
        assertFalse(desktopNavigation.contains("<a "));
        assertEquals(3, desktopNavigation.split("<button", -1).length - 1);
    }

    private String dock(String html, String id) {
        int start = html.indexOf("id=\"" + id + "\"");
        assertTrue(start >= 0, "Missing service dock: " + id);
        int end = html.indexOf("</section>", start);
        assertTrue(end > start);
        return html.substring(start, end);
    }

    private int countCards(String html) {
        return html.split("class=\"service-card\"", -1).length - 1;
    }

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
