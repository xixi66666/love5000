package com.example.website;

import org.junit.jupiter.api.Test;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;

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
        assertTrue(html.contains("data-health-url=\"/api/services/local/strata/health\""));
        assertTrue(html.contains("data-health-url=\"/api/services/local/aimedia/health\""));
        assertTrue(html.contains("data-health-url=\"/api/services/local/h3/health\""));
        assertTrue(html.contains("data-auth-required=\"true\""));
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
