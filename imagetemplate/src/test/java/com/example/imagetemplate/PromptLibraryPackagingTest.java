package com.example.imagetemplate;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;

import static org.assertj.core.api.Assertions.assertThat;

class PromptLibraryPackagingTest {

    @Test
    void promptConsoleLibraryIsCopiedIntoImageTemplateClasspath() throws Exception {
        ClassPathResource resource =
                new ClassPathResource("templates/prompt-console/prompt-library.json");

        assertThat(resource.exists()).isTrue();
        JsonNode root = new ObjectMapper().readTree(resource.getInputStream());
        assertThat(root.path("sources").size()).isEqualTo(6);
        assertThat(root.path("entries").size()).isEqualTo(4409);
    }
}
