package com.example.website.integration.models;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.mock.env.MockEnvironment;
import org.springframework.web.server.ResponseStatusException;
import java.nio.file.*;
import java.util.*;
import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class ModelRoutingServiceTest {
    @TempDir Path dir;
    ObjectMapper json=new ObjectMapper();
    ModelHttp http;
    ModelSources sources;
    ModelRoutingService service;
    @BeforeEach void setup()throws Exception {
        http=mock(ModelHttp.class);sources=mock(ModelSources.class);
        when(sources.strataHome()).thenReturn(dir);
        when(sources.read()).thenReturn(Arrays.asList(
                new ModelSources.Source("deepseek","DeepSeek","https://test.example/v1","private-test-key","flash,pro"),
                new ModelSources.Source("strata","本机 Qwen","http://127.0.0.1:9999/v1","","")));
        when(http.request(eq("https://test.example/v1/models"),anyString(),isNull(),anyInt()))
                .thenReturn(json.readTree("{\"data\":[{\"id\":\"flash\"},{\"id\":\"pro\"},{\"id\":\"gpt-image-test\"}]}"));
        when(http.request(eq("http://127.0.0.1:9999/v1/models"),anyString(),isNull(),anyInt())).thenThrow(new java.io.IOException("private-upstream-detail"));
        when(http.request(endsWith("/chat/completions"),anyString(),any(JsonNode.class),anyInt())).thenAnswer(a->{
            ObjectNode result=json.createObjectNode();result.put("model",((JsonNode)a.getArgument(2)).path("model").asText());return result;
        });
        service=new ModelRoutingService(json,sources,http,dir.resolve("selection.json"));
    }
    @Test void globalAndServiceOverrideRouteActualPayloadAndCredentials()throws Exception {
        service.select("global","deepseek:flash");
        service.select("skill-finder","deepseek:pro");
        ObjectNode request=(ObjectNode)json.readTree("{\"model\":\"ignored\",\"messages\":[{\"role\":\"user\",\"content\":\"hello\"}]}");
        assertThat(service.chat("python-a",request).path("model").asText()).isEqualTo("flash");
        assertThat(service.chat("skill-finder",request).path("model").asText()).isEqualTo("pro");
        service.select("global","deepseek:pro");
        assertThat(service.effective("skill-finder").get("modelId")).isEqualTo("deepseek:pro");
        service.select("skill-finder","");
        assertThat(service.effective("skill-finder").get("inherited")).isEqualTo(true);
        verify(http,atLeastOnce()).request(eq("https://test.example/v1/chat/completions"),eq("private-test-key"),any(JsonNode.class),anyInt());
        assertThat(request.path("model").asText()).isEqualTo("ignored");
    }
    @Test void nativeOverrideAndRestartPersistenceNeverExposeCredentials()throws Exception {
        service.select("global","deepseek:flash");service.select("personal-agent","native");
        assertThat(service.effective("personal-agent").get("active")).isEqualTo(false);
        ModelRoutingService restarted=new ModelRoutingService(json,sources,http,dir.resolve("selection.json"));
        assertThat(restarted.effective("python-a").get("modelId")).isEqualTo("deepseek:flash");
        assertThat(json.writeValueAsString(service.catalog(false))).doesNotContain("private-test-key","test.example","private-upstream-detail");
        assertThat(new String(Files.readAllBytes(dir.resolve("selection.json")),java.nio.charset.StandardCharsets.UTF_8)).doesNotContain("private-test-key");
    }
    @Test void unavailableUnknownAndImageChoicesCannotBeSaved() {
        assertThatThrownBy(()->service.select("global","strata:Qwen3.8-Flash-Next")).isInstanceOf(ResponseStatusException.class);
        assertThatThrownBy(()->service.select("global","deepseek:gpt-image-test")).isInstanceOf(ResponseStatusException.class);
        assertThatThrownBy(()->service.select("unknown","deepseek:flash")).isInstanceOf(ResponseStatusException.class);
        assertThat(service.effective("python-a").get("active")).isEqualTo(false);
    }
    @Test void failedPersistenceDoesNotChangeActiveSelection()throws Exception {
        Path file=dir.resolve("blocked");Files.write(file,new byte[]{1});
        ModelRoutingService broken=new ModelRoutingService(json,sources,http,file.resolve("state.json"));
        assertThatThrownBy(()->broken.select("global","deepseek:flash")).isInstanceOf(ResponseStatusException.class);
        assertThat(broken.effective("python-a").get("active")).isEqualTo(false);
    }
    @Test void upstreamFailureDoesNotFallbackAndRejectsImages()throws Exception {
        service.select("global","deepseek:flash");
        when(http.request(endsWith("/chat/completions"),anyString(),any(JsonNode.class),anyInt())).thenThrow(new java.io.IOException("secret failure"));
        ObjectNode payload=(ObjectNode)json.readTree("{\"messages\":[{\"content\":\"hello\"}]}");
        ObjectNode textRequest=payload;
        assertThatThrownBy(()->service.chat("python-a",textRequest)).hasMessageNotContaining("secret failure");
        verify(http,times(1)).request(endsWith("/chat/completions"),anyString(),any(JsonNode.class),anyInt());
        payload=(ObjectNode)json.readTree("{\"messages\":[{\"content\":[{\"type\":\"image_url\"}]}]}");
        ObjectNode images=payload;
        assertThatThrownBy(()->service.chat("python-a",images)).hasMessageContaining("文本");
    }
    @Test void privateFileSourceIsReadWithoutCopying()throws Exception {
        Path config=dir.resolve("website/python-a");Files.createDirectories(config);
        Files.write(config.resolve("deepseek.local.json"),"{\"DEEPSEEK_API_KEY\":\"private-test-key\"}".getBytes(java.nio.charset.StandardCharsets.UTF_8));
        ModelSources actual=new ModelSources(new MockEnvironment(),json,dir);
        assertThat(actual.read().get(0).key).isEqualTo("private-test-key");
    }
}
