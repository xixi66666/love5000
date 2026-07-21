package com.example.guitar.config;

import com.example.guitar.GuitarApplication;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.net.URISyntaxException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

import static org.assertj.core.api.Assertions.assertThat;

class GuitarRuntimeConfigurationTest {

    @Test
    void mainRuntimeConfigurationDefinesGuitarSessionCookie() throws IOException, URISyntaxException {
        Path mainClassesDirectory = Paths.get(GuitarApplication.class.getProtectionDomain()
                .getCodeSource().getLocation().toURI());
        String configuration = new String(Files.readAllBytes(mainClassesDirectory.resolve("application.yml")),
                StandardCharsets.UTF_8);

        assertThat(configuration).contains(
                "name: GUITARSESSIONID",
                "http-only: true",
                "same-site: lax",
                "secure: ${GUITAR_SESSION_COOKIE_SECURE:false}");
    }
}
