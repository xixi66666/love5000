package com.example.imagetemplate.service;

import com.example.imagetemplate.dto.*;
import org.junit.jupiter.api.Test;
import org.springframework.mock.env.MockEnvironment;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestTemplate;
import org.springframework.http.MediaType;
import java.lang.reflect.Field;
import static org.assertj.core.api.Assertions.*;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;

class ImageModelSelectionTest {
    @Test void selectedModelIsSentAndReturnedWithoutChangingDefault()throws Exception {
        OpenAiImageGenerationService service=new OpenAiImageGenerationService(null,new MockEnvironment()
                .withProperty("openai.api-key","test-only").withProperty("openai.base-url","https://images.example/v1")
                .withProperty("openai.image-model","gpt-image-2.5-sunburst"));
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
