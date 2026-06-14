package com.example.website.prompt;

import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;

import static org.assertj.core.api.Assertions.assertThat;

class PromptLibraryStaticPageTest {

    @Test
    void promptConsoleIsLibraryPageWithoutComposerApi() throws Exception {
        String html = read("website/src/main/resources/static/prompt-console/index.html");
        String js = read("website/src/main/resources/static/prompt-console/prompt-console.js");

        assertThat(html)
                .contains("Prompt Library")
                .contains("提示词合集")
                .doesNotContain("场景生成器")
                .doesNotContain("多源比对生成");
        assertThat(js)
                .contains("data/prompt-library.json")
                .doesNotContain("/api/prompts/compose")
                .doesNotContain("compose(");
    }

    @Test
    void promptLibraryDataContainsImportedEntries() throws Exception {
        String json = read("website/src/main/resources/static/prompt-console/data/prompt-library.json");

        assertThat(json)
                .contains("\"authorizedByUser\": true")
                .contains("\"sourceId\": \"awesome-chatgpt-prompts\"")
                .contains("\"sourceId\": \"freestylefly-awesome-gpt-image-2\"")
                .contains("\"prompt\":");
    }

    private String read(String path) throws Exception {
        String moduleRelativePath = path.replace("website/", "");
        return new String(Files.readAllBytes(Paths.get(moduleRelativePath)), StandardCharsets.UTF_8);
    }
}
