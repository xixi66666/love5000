package com.example.website.prompt.service;

import com.example.website.prompt.dto.PromptComposeRequest;
import com.example.website.prompt.model.PromptVariant;
import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * 提示词拼装服务 {@link PromptComposeService} 的单元测试。
 *
 * <p>被测逻辑是纯字符串模板拼装，不碰数据库和网络：场景为空白时抛
 * {@link IllegalArgumentException}（消息含「场景不能为空」）；{@code purpose} 决定排在第一位的变体
 * （image / video / poster / general），其后补齐 general、image、video、poster、short 五种形态；
 * 图片版必须带上『镜头』『光线』『构图』和「不要出现乱码文字、水印、额外 logo」的负面限制；
 * 视频版换成三个镜头的分镜语言，且不残留图片模板的占位说明；选中的来源快照会以
 * 「参考来源综合」前缀注入正文，未选中的来源不得出现，{@code sourceIds} 原样回传。</p>
 *
 * <p>隔离：{@link PromptSourceRegistry} 用真实实例（白名单是常量），抓取服务注入返回固定文本的假
 * HTTP 客户端，因此不联网、也不依赖 MySQL；拼装过程没有随机分支，断言可以逐字比对关键词。</p>
 */
class PromptComposeServiceTest {

    private final PromptSourceRegistry registry = new PromptSourceRegistry();
    private final PromptComposeService service = new PromptComposeService(
            registry,
            new PromptSourceFetchService(registry));

    @Test
    void composeRejectsBlankScene() {
        PromptComposeRequest request = new PromptComposeRequest();
        request.setScene(" ");

        assertThatThrownBy(() -> service.compose(request))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("场景不能为空");
    }

    @Test
    void composeImagePromptIncludesVisualStructureAndNegativeLimits() {
        PromptComposeRequest request = new PromptComposeRequest();
        request.setScene("雨夜城市街巷，想做一张电影感海报");
        request.setPurpose("image");
        request.setTone("cinematic");
        request.setLength("balanced");

        List<PromptVariant> variants = service.compose(request);

        assertThat(variants).extracting(PromptVariant::getType)
                .contains("image", "general", "poster", "video", "short");
        assertThat(variants.get(0).getType()).isEqualTo("image");
        assertThat(variants.get(0).getPrompt())
                .contains("雨夜城市街巷")
                .contains("镜头")
                .contains("光线")
                .contains("构图")
                .contains("不要出现乱码文字、水印、额外 logo");
    }

    @Test
    void composeVideoPromptIncludesStoryboardLanguage() {
        PromptComposeRequest request = new PromptComposeRequest();
        request.setScene("一只可爱的小猫在追逐蝴蝶");
        request.setPurpose("video");

        List<PromptVariant> variants = service.compose(request);

        assertThat(variants.get(0).getType()).isEqualTo("video");
        assertThat(variants.get(0).getPrompt())
                .contains("镜头 1")
                .contains("镜头 2")
                .contains("镜头 3")
                .contains("小猫")
                .contains("蝴蝶")
                .contains("跟拍")
                .contains("光线")
                .contains("声音")
                // 回归：图片版模板里的占位说明不能漏进视频分镜正文。
                .doesNotContain("按镜头 1、镜头 2、镜头 3 描述画面推进");
    }

    @Test
    void composeUsesSelectedSourceSnapshotsAsGenerationGuidance() {
        PromptSourceRegistry registry = new PromptSourceRegistry();
        PromptSourceFetchService fetchService = new PromptSourceFetchService(
                registry,
                new PromptSourceSummaryService(),
                url -> "结构化模板要求：主体、场景、镜头、光线、构图、负面限制；商业视觉要求：卖点层级、摄影质感。");
        fetchService.refresh(Arrays.asList("prompt123", "freestylefly-awesome-gpt-image-2"));
        PromptComposeService sourceAwareService = new PromptComposeService(registry, fetchService);

        PromptComposeRequest request = new PromptComposeRequest();
        request.setScene("赛博朋克茶馆宣传图");
        request.setPurpose("image");
        request.setSourceIds(Arrays.asList("freestylefly-awesome-gpt-image-2"));

        List<PromptVariant> variants = sourceAwareService.compose(request);

        assertThat(variants.get(0).getPrompt())
                .contains("参考来源综合")
                .contains("freestylefly GPT Image 2")
                .contains("结构化模板")
                .contains("主体、场景、镜头、光线、构图、负面限制")
                .doesNotContain("Prompt123");
        assertThat(variants.get(0).getSourceIds()).containsExactly("freestylefly-awesome-gpt-image-2");
    }
}
