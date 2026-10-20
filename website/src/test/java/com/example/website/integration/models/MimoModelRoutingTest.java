package com.example.website.integration.models;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.mock.env.MockEnvironment;
import org.springframework.web.server.ResponseStatusException;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Collections;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class MimoModelRoutingTest {
    @TempDir Path dir;
    private final ObjectMapper json = new ObjectMapper();
    private ModelHttp http;
    private ModelRoutingService service;

    @BeforeEach void setup() throws Exception {
        http = mock(ModelHttp.class);
        ModelSources sources = mock(ModelSources.class);
        when(sources.strataHome()).thenReturn(dir);
        when(sources.read()).thenReturn(Collections.singletonList(new ModelSources.Source(
                "mimo", "Xiaomi MiMo", "https://mimo.example/v1", "test-mimo-key",
                "mimo-v2.6-pro,mimo-v2.6-flash")));
        when(http.request(endsWith("/models"), anyString(), isNull(), anyInt())).thenReturn(json.readTree(
                "{\"data\":[{\"id\":\"mimo-v2.6-pro\"},{\"id\":\"mimo-v2.6-flash\"},"
                + "{\"id\":\"mimo-v2.6-pro-ultraspeed\"},{\"id\":\"mimo-v2.5\"},"
                + "{\"id\":\"mimo-v2.5-tts\"},{\"id\":\"mimo-v2.5-asr\"}]}"));
        when(http.request(endsWith("/chat/completions"), anyString(), any(JsonNode.class), anyInt()))
                .thenAnswer(call -> ((JsonNode) call.getArgument(2)).deepCopy());
        service = new ModelRoutingService(json, sources, http, dir.resolve("selection.json"));
    }

    @Test void readsExistingPrivateKeyAndEnvironmentWinsWithoutChangingTts() throws Exception {
        Path config = dir.resolve("website/skill-finder/backend/.env");
        Files.createDirectories(config.getParent());
        String original = "MIMO_API_KEY='test-local-key'\nMIMO_TTS_MODEL=mimo-v2.5-tts\n";
        Files.write(config, original.getBytes(StandardCharsets.UTF_8));
        ModelSources local = new ModelSources(new MockEnvironment(), json, dir);
        ModelSources.Source fromFile = local.read().stream().filter(s -> "mimo".equals(s.id)).findFirst().get();
        assertThat(fromFile.key).isEqualTo("test-local-key");
        assertThat(fromFile.base).isEqualTo("https://api.xiaomimimo.com/v1");
        assertThat(fromFile.configured).containsExactly("mimo-v2.6-pro", "mimo-v2.6-flash");
        ModelSources env = new ModelSources(new MockEnvironment().withProperty("MIMO_API_KEY", "test-env-key")
                .withProperty("MIMO_CHAT_MODELS", "mimo-v2.6-flash"), json, dir);
        ModelSources.Source override = env.read().stream().filter(s -> "mimo".equals(s.id)).findFirst().get();
        assertThat(override.key).isEqualTo("test-env-key");
        assertThat(override.configured).containsExactly("mimo-v2.6-flash");
        assertThat(new String(Files.readAllBytes(config), StandardCharsets.UTF_8)).isEqualTo(original);
    }

    @Test void directoryExcludesSpeechRetiringAndCustomModels() throws Exception {
        JsonNode catalog = json.valueToTree(service.catalog(false));
        assertThat(catalog.path("models").size()).isEqualTo(2);
        assertThat(catalog.toString()).contains("mimo-v2.6-pro", "mimo-v2.6-flash")
                .doesNotContain("test-mimo-key", "mimo.example", "mimo-v2.5", "ultraspeed");
        assertThatThrownBy(() -> service.select("global", "mimo:mimo-v2.5-asr"))
                .isInstanceOf(ResponseStatusException.class);
        assertThat(ModelRoutingService.isChatModel("mimo-v2.5-asr")).isFalse();
    }

    @Test void globalAndLocalSelectionsUseMimoAndNormalizeTokenBudget() throws Exception {
        service.select("global", "mimo:mimo-v2.6-pro");
        service.select("scrapling-ui", "mimo:mimo-v2.6-flash");
        ObjectNode input = (ObjectNode) json.readTree("{\"messages\":[{\"role\":\"user\",\"content\":\"Return JSON\"}],"
                + "\"max_tokens\":150,\"response_format\":{\"type\":\"json_object\"}}");
        JsonNode pro = service.chat("personal-agent", input);
        assertThat(pro.path("model").asText()).isEqualTo("mimo-v2.6-pro");
        assertThat(pro.path("max_completion_tokens").asInt()).isEqualTo(150);
        assertThat(pro.has("max_tokens")).isFalse();
        assertThat(pro.path("thinking").path("type").asText()).isEqualTo("disabled");
        assertThat(pro.path("response_format").path("type").asText()).isEqualTo("json_object");
        assertThat(service.chat("scrapling-ui", input).path("model").asText()).isEqualTo("mimo-v2.6-flash");
        assertThat(input.has("max_tokens")).isTrue();
        assertThat(input.has("thinking")).isFalse();
        verify(http, atLeastOnce()).request(eq("https://mimo.example/v1/chat/completions"),
                eq("test-mimo-key"), any(JsonNode.class), anyInt());
    }

    @Test void explicitBudgetAndThinkingArePreservedWithCompatibleSampling() throws Exception {
        service.select("global", "mimo:mimo-v2.6-pro");
        ObjectNode input = (ObjectNode) json.readTree("{\"messages\":[{\"content\":\"hello\"}],"
                + "\"max_tokens\":150,\"max_completion_tokens\":2048,\"thinking\":{\"type\":\"enabled\"},"
                + "\"temperature\":0.1,\"top_p\":0.5}");
        JsonNode output = service.chat("python-a", input);
        assertThat(output.path("max_completion_tokens").asInt()).isEqualTo(2048);
        assertThat(output.path("thinking").path("type").asText()).isEqualTo("enabled");
        assertThat(output.has("temperature")).isFalse();
        assertThat(output.has("top_p")).isFalse();
        assertThat(output.has("max_tokens")).isFalse();
        input.remove(java.util.Arrays.asList("max_tokens", "max_completion_tokens", "thinking"));
        assertThat(service.chat("skill-finder", input).path("max_completion_tokens").asInt()).isEqualTo(8192);
    }

    @Test void missingOrRejectedCredentialsCannotBeSelected() throws Exception {
        when(http.request(endsWith("/models"), anyString(), isNull(), anyInt()))
                .thenThrow(new java.io.IOException("private authorization error"));
        JsonNode catalog = json.valueToTree(service.catalog(true));
        assertThat(catalog.path("models").get(0).path("available").asBoolean()).isFalse();
        assertThat(catalog.toString()).doesNotContain("private authorization error", "test-mimo-key");
        assertThatThrownBy(() -> service.select("global", "mimo:mimo-v2.6-pro"))
                .isInstanceOf(ResponseStatusException.class);
    }
}
