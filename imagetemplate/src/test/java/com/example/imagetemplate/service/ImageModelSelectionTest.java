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
        Field f=OpenAiImageGenerationService.class.getDeclaredField("restTemplate");f.setAccessible(true);
        MockRestServiceServer server=MockRestServiceServer.bindTo((RestTemplate)f.get(service)).build();
        server.expect(requestTo("https://images.example/v1/images/generations"))
                .andExpect(jsonPath("$.model").value("gpt-image-2.5-flare"))
                .andRespond(withSuccess("{\"data\":[{\"b64_json\":\"aGVsbG8=\"}]}",MediaType.APPLICATION_JSON));
        ImageGenerationRequest request=new ImageGenerationRequest();request.setPrompt("test");request.setModel("gpt-image-2.5-flare");
        assertThat(service.generate("direct",request).getModel()).isEqualTo("gpt-image-2.5-flare");server.verify();
        assertThat(service.modelOptions().get("defaultModel")).isEqualTo("gpt-image-2.5-sunburst");
        request.setModel("deepseek-flash");
        assertThatThrownBy(()->service.generate("direct",request)).isInstanceOf(ImageGenerationException.class).hasMessageContaining("不支持");
    }
}
