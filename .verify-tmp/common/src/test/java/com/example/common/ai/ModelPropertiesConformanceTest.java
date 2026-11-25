package com.example.common.ai;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * 与 website/model-routing 共用同一组合成 properties 用例，防止 Java/Python 解析语义漂移。
 */
class ModelPropertiesConformanceTest {

    private static final ObjectMapper JSON = new ObjectMapper();
    private static final String CONFORMANCE_FILE = "website/model-routing/conformance/cases.json";

    @TempDir
    Path dir;

    @Test
    void matchesSharedJavaPropertiesConformanceCases() throws Exception {
        JsonNode cases = JSON.readTree(conformanceFile().toFile()).path("cases");
        assertThat(cases.isArray()).isTrue();

        for (JsonNode testCase : cases) {
            String name = testCase.path("name").asText();
            Path file = dir.resolve(name + ".properties");
            Files.write(file, testCase.path("content").asText().getBytes(StandardCharsets.UTF_8));

            if (testCase.has("error")) {
                assertThatThrownBy(() -> ModelProperties.load(file))
                        .as("case %s must reject malformed properties", name)
                        .isInstanceOf(IllegalArgumentException.class);
                continue;
            }

            ModelProperties settings = ModelProperties.load(file);
            assertThat(settings.exists()).as("case %s exists", name).isTrue();

            List<ModelProperties.Provider> providers =
                    new ArrayList<ModelProperties.Provider>(settings.providers());
            JsonNode expectedProviders = testCase.path("providers");
            assertThat(providers).as("case %s provider count", name).hasSize(expectedProviders.size());
            for (int i = 0; i < expectedProviders.size(); i++) {
                assertProvider(name, providers.get(i), expectedProviders.get(i));
            }

            JsonNode routes = testCase.path("routes");
            for (Iterator<Map.Entry<String, JsonNode>> iterator = routes.fields(); iterator.hasNext(); ) {
                Map.Entry<String, JsonNode> entry = iterator.next();
                String scope = entry.getKey();
                JsonNode expected = entry.getValue();
                ModelProperties.Route route = settings.route(scope);
                if (expected.isNull()) {
                    assertThat(route).as("case %s route %s", name, scope).isNull();
                } else {
                    assertThat(route).as("case %s route %s", name, scope).isNotNull();
                    assertThat(route.id()).as("case %s route %s", name, scope).isEqualTo(expected.asText());
                }
            }
        }
    }

    private static void assertProvider(String caseName, ModelProperties.Provider provider, JsonNode expected) {
        String providerId = expected.path("id").asText();
        assertThat(provider.id()).as("case %s provider id", caseName).isEqualTo(providerId);
        assertThat(provider.label()).as("case %s provider label", caseName).isEqualTo(expected.path("label").asText());
        assertThat(provider.baseUrl()).as("case %s provider baseUrl", caseName)
                .isEqualTo(expected.path("baseUrl").asText());
        assertThat(provider.apiKey()).as("case %s provider apiKey", caseName)
                .isEqualTo(expected.path("apiKey").asText());
        assertThat(provider.capability()).as("case %s provider capability", caseName)
                .isEqualTo(expected.path("capability").asText());

        List<String> models = new ArrayList<String>();
        for (JsonNode model : expected.path("models")) models.add(model.asText());
        assertThat(provider.models()).as("case %s provider models", caseName)
                .containsExactlyElementsOf(models);

        JsonNode options = expected.path("options");
        for (Iterator<Map.Entry<String, JsonNode>> iterator = options.fields(); iterator.hasNext(); ) {
            Map.Entry<String, JsonNode> entry = iterator.next();
            assertThat(provider.option(entry.getKey()))
                    .as("case %s provider option %s", caseName, entry.getKey())
                    .isEqualTo(entry.getValue().asText());
        }
    }

    private static Path conformanceFile() {
        Path current = Paths.get("").toAbsolutePath().normalize();
        for (Path candidate = current; candidate != null; candidate = candidate.getParent()) {
            Path file = candidate.resolve(CONFORMANCE_FILE);
            if (Files.isRegularFile(file)) return file;
        }
        throw new IllegalStateException("找不到跨实现一致性用例：" + CONFORMANCE_FILE);
    }
}
