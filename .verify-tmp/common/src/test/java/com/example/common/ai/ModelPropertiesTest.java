package com.example.common.ai;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.assertj.core.api.Assertions.assertThat;

class ModelPropertiesTest {

    @TempDir
    Path dir;

    private ModelProperties load(String content) throws Exception {
        Path file = dir.resolve("model.properties");
        Files.write(file, content.getBytes(StandardCharsets.UTF_8));
        return ModelProperties.load(file);
    }

    @Test
    void readsProvidersAndServiceRoutes() throws Exception {
        ModelProperties settings = load(
                "deepseek.label=DeepSeek\n"
                        + "deepseek.base-url=https://api.deepseek.com/\n"
                        + "deepseek.api-key=test-key\n"
                        + "deepseek.models=deepseek-flash, deepseek-v4-pro\n"
                        + "mimo.base-url=https://api.xiaomimimo.com/v1\n"
                        + "mimo.capability=text\n"
                        + "mimo.models=mimo-v2.6-pro\n"
                        + "mimo.tts-model=mimo-v2.5-tts\n"
                        + "image.base-url=https://images.example/v1\n"
                        + "image.capability=image\n"
                        + "image.image-model=gpt-image-test\n"
                        + "service.global=deepseek:deepseek-flash\n"
                        + "service.python-a=deepseek:deepseek-v4-pro\n"
                        + "service.personal-agent=deepseek:deepseek-flash\n");

        assertThat(settings.exists()).isTrue();
        assertThat(settings.textProviders()).extracting(ModelProperties.Provider::id)
                .containsExactly("deepseek", "mimo");
        ModelProperties.Provider deepseek = settings.provider("deepseek");
        assertThat(deepseek.label()).isEqualTo("DeepSeek");
        assertThat(deepseek.baseUrl()).isEqualTo("https://api.deepseek.com");
        assertThat(deepseek.apiKey()).isEqualTo("test-key");
        assertThat(deepseek.models()).containsExactly("deepseek-flash", "deepseek-v4-pro");
        assertThat(settings.provider("mimo").option("tts-model")).isEqualTo("mimo-v2.5-tts");
        assertThat(settings.provider("image").text()).isFalse();
        assertThat(settings.provider("missing")).isNull();

        assertThat(settings.route("python-a").id()).isEqualTo("deepseek:deepseek-v4-pro");
        assertThat(settings.route("skill-finder").id()).isEqualTo("deepseek:deepseek-flash");
    }

    @Test
    void missingFileYieldsEmptyCatalogAndNoRoute() throws Exception {
        ModelProperties settings = ModelProperties.load(dir.resolve("missing.properties"));
        assertThat(settings.exists()).isFalse();
        assertThat(settings.providers()).isEmpty();
        assertThat(settings.route("python-a")).isNull();
    }

    @Test
    void invalidRoutesAndProvidersAreIgnored() throws Exception {
        ModelProperties settings = load(
                "deepseek.base-url=https://api.deepseek.com\n"
                        + "service.python-a=unknown:some-model\n"
                        + "service.skill-finder=broken\n"
                        + "service.personal-agent=deepseek:\n");
        assertThat(settings.route("python-a")).isNull();
        assertThat(settings.route("skill-finder")).isNull();
        assertThat(settings.route("personal-agent")).isNull();
    }
}
