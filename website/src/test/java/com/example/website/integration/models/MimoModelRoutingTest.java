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

/**
 * MiMo（Xiaomi MiMo V2.6）在统一模型路由中的行为测试。
 *
 * <p>被测对象是 {@link ModelRoutingService}。本类用 mock 的 {@link ModelHttp} 代替真实网关、
 * 用 mock 的 {@link ModelSources} 提供固定的配置内容，选择状态文件落在 {@link TempDir} 里，
 * 因此不联网、不使用真实密钥、不写仓库文件。</p>
 *
 * <p>固定的关键规则：</p>
 * <ul>
 *   <li>模型目录只来自 {@code model.properties}，读取时不得回写或改写原文件；</li>
 *   <li>目录与真实 {@code /models} 取交集，并过滤 TTS / ASR / 旧版与未显式配置的定制型号；</li>
 *   <li>选择接口拒绝非文本模型与不可用模型，避免主页选中一个永远调不通的模型；</li>
 *   <li>按官方规范把 {@code max_tokens} 转成 {@code max_completion_tokens}（缺省 8192），
 *       默认关闭深度思考；显式开启思考时移除 {@code temperature} 与 {@code top_p}；</li>
 *   <li>密钥与上游异常原文不得出现在目录或错误响应里。</li>
 * </ul>
 */
class MimoModelRoutingTest {
    @TempDir Path dir;
    private final ObjectMapper json = new ObjectMapper();
    private ModelHttp http;
    private ModelRoutingService service;

    /**
     * 装配两件替身。
     *
     * <p>{@link ModelSources} 固定返回一条 MiMo 配置；{@link ModelHttp} 同时伪装目录与生成：
     * {@code /models} 特意混入 TTS、ASR、旧版和定制型号，用来验证目录过滤；生成接口把入参深拷贝
     * 后回传，既方便断言真正发出的请求体，也证明调用方入参没有被就地改写。</p>
     */
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

    @Test void modelPropertiesDrivesMimoCatalogWithoutReadingOtherFiles() throws Exception {
        Path config = dir.resolve("model.properties");
        String original = "mimo.label=Xiaomi MiMo\n"
                + "mimo.base-url=https://api.xiaomimimo.com/v1\n"
                + "mimo.api-key=test-local-key\n"
                + "mimo.models=mimo-v2.6-pro,mimo-v2.6-flash\n"
                + "mimo.tts-model=mimo-v2.5-tts\n";
        Files.write(config, original.getBytes(StandardCharsets.UTF_8));
        ModelSources local = new ModelSources(new MockEnvironment(), dir);
        ModelSources.Source fromFile = local.read().stream().filter(s -> "mimo".equals(s.id)).findFirst().get();
        assertThat(fromFile.key).isEqualTo("test-local-key");
        assertThat(fromFile.base).isEqualTo("https://api.xiaomimimo.com/v1");
        assertThat(fromFile.configured).containsExactly("mimo-v2.6-pro", "mimo-v2.6-flash");
        // 读取配置不能回写文件：与原内容逐字比较，任何格式化或密钥回填都会暴露。
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
        // 去掉显式预算后应回落到默认 8192，而不是沿用上一次请求的值。
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
