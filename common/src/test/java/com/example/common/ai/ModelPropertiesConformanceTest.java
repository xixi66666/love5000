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

    /**
     * 逐字段比对单个提供商，确认字段名、列表顺序与可选配置都与共享用例一致。
     *
     * @param caseName 用例名，用于断言失败时定位
     * @param provider 实际解析出的提供商
     * @param expected 共享用例中声明的期望值
     */
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

    /**
     * 从当前工作目录向上查找共享一致性用例文件。
     *
     * <p>Maven 可能以模块目录或仓库根目录为工作目录，所以不能写死相对路径；
     * 找不到时直接失败，避免测试被静默跳过。</p>
     *
     * @return 用例文件的绝对路径
     * @throws IllegalStateException 一路向上都没有找到用例文件时抛出
     */
    private static Path conformanceFile() {
        Path current = Paths.get("").toAbsolutePath().normalize();
        for (Path candidate = current; candidate != null; candidate = candidate.getParent()) {
            Path file = candidate.resolve(CONFORMANCE_FILE);
            if (Files.isRegularFile(file)) return file;
        }
        throw new IllegalStateException("找不到跨实现一致性用例：" + CONFORMANCE_FILE);
    }
}
