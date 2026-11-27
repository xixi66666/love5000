package com.example.imagetemplate;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 打包契约测试：Maven 构建必须把 website 模块中唯一维护的 Prompt Console 大库复制到
 * imagetemplate 的 classpath（{@code templates/prompt-console/prompt-library.json}）。
 *
 * <p>断言资源存在，且来源为 6 个、条目为 4409 条。任一数字变化都会影响聚合总量 4456 与
 * 页面来源统计，因此问题必须在构建阶段暴露，而不是等运行时才发现大库缺失。测试直接读取
 * classpath JSON，不启动 Spring 上下文、不联网。</p>
 */
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
