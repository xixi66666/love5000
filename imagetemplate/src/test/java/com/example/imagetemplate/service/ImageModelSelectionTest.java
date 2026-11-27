package com.example.imagetemplate.service;

import com.example.common.ai.ModelProperties;
import com.example.imagetemplate.dto.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestTemplate;
import org.springframework.http.MediaType;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import static org.assertj.core.api.Assertions.*;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;

/**
 * 图片模型选择的透传与白名单测试。
 *
 * <p>覆盖三条行为：{@code image.image-models} 白名单中的模型会写入请求体 {@code model}
 * 并回写到响应；服务上报的默认模型仍是 {@code image.image-model}，选择白名单模型不会改写
 * 默认值；不在白名单中的模型会在发出 HTTP 之前被 {@link ImageGenerationException} 拒绝。</p>
 *
 * <p>隔离手段：配置文件写入 JUnit {@code @TempDir} 临时目录，再通过反射取出服务内部的
 * {@code RestTemplate} 交给 {@code MockRestServiceServer} 接管，请求与响应全部在内存中
 * 完成，不访问真实图片服务。</p>
 */
class ImageModelSelectionTest {
    @TempDir Path dir;

    @Test void selectedModelIsSentAndReturnedWithoutChangingDefault()throws Exception {
        Path config=dir.resolve("model.properties");
        Files.write(config,("image.base-url=https://images.example/v1\n"
                +"image.api-key=test-only\n"
                +"image.image-model=gpt-image-2.5-sunburst\n"
                +"image.image-models=gpt-image-2.5-sunburst,gpt-image-2.5-flare\n")
                .getBytes(StandardCharsets.UTF_8));
        OpenAiImageGenerationService service=new OpenAiImageGenerationService(
                null,ModelProperties.load(config).provider("image"));
        // 反射取出内部 RestTemplate，交给 MockRestServiceServer 接管，避免真实出网。
        Field f=OpenAiImageGenerationService.class.getDeclaredField("restTemplate");f.setAccessible(true);
        MockRestServiceServer server=MockRestServiceServer.bindTo((RestTemplate)f.get(service)).build();
        server.expect(requestTo("https://images.example/v1/images/generations"))
                .andExpect(jsonPath("$.model").value("gpt-image-2.5-flare"))
                .andRespond(withSuccess("{\"data\":[{\"b64_json\":\"aGVsbG8=\"}]}",MediaType.APPLICATION_JSON));
        ImageGenerationRequest request=new ImageGenerationRequest();request.setPrompt("test");request.setModel("gpt-image-2.5-flare");
        assertThat(service.generate("direct",request).getModel()).isEqualTo("gpt-image-2.5-flare");server.verify();
        assertThat(service.modelOptions().get("defaultModel")).isEqualTo("gpt-image-2.5-sunburst");
        // 文本模型不在图片白名单内，必须在触网前被拒绝。
        request.setModel("deepseek-flash");
        assertThatThrownBy(()->service.generate("direct",request)).isInstanceOf(ImageGenerationException.class).hasMessageContaining("不支持");
    }
}
