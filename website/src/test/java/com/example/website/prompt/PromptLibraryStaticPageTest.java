package com.example.website.prompt;

import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 提示词库静态页面的契约测试。
 *
 * <p>第一个用例确认页面定位已经从「场景生成器」收敛为纯提示词合集：
 * 文案保留 {@code Prompt Archive}、「提示词合集」「添加提示词」，不再出现「场景生成器」「多源比对生成」；
 * 脚本只走服务端接口（引用 {@code /api/prompts/meta}），不再读取本地的
 * {@code data/prompt-library.json}，也不再调用已下线的 {@code /api/prompts/compose}。
 * 第二个用例守住唯一源数据文件仍带着导入标记（{@code authorizedByUser}、两个来源 ID 与正文字段），
 * 导入脚本或数据重生成若丢字段会先在这里失败。</p>
 *
 * <p>隔离：按文件路径直接读源码文本，不起 Spring、不发请求、不连 MySQL；
 * 路径解析依赖 Maven 以模块目录为工作目录，见 {@link #read(String)}。</p>
 */
class PromptLibraryStaticPageTest {

    @Test
    void promptConsoleIsLibraryPageWithoutComposerApi() throws Exception {
        String html = read("website/src/main/resources/static/prompt-console/index.html");
        String js = read("website/src/main/resources/static/prompt-console/prompt-console.js");

        assertThat(html)
                .contains("Prompt Archive")
                .contains("提示词合集")
                .contains("添加提示词")
                .doesNotContain("场景生成器")
                .doesNotContain("多源比对生成");
        assertThat(js)
                .contains("/api/prompts/meta")
                .doesNotContain("data/prompt-library.json")
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

    /**
     * 读取模块内的静态资源文本。
     *
     * <p>路径按仓库根书写（{@code website/src/...}），而测试运行时 Maven 的工作目录是模块目录，
     * 因此先裁掉 {@code website/} 前缀；这样从仓库根或模块目录触发都能命中同一份文件。</p>
     */
    private String read(String path) throws Exception {
        String moduleRelativePath = path.replace("website/", "");
        return new String(Files.readAllBytes(Paths.get(moduleRelativePath)), StandardCharsets.UTF_8);
    }
}
