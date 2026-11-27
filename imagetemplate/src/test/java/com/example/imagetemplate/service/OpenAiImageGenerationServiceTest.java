package com.example.imagetemplate.service;

import com.example.common.ai.ModelProperties;
import com.example.imagetemplate.dto.ImageGenerationRequest;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * {@link OpenAiImageGenerationService} 的尺寸校验与模型配置测试。
 *
 * <p>通过反射直接测试私有方法 {@code normalizeImageSize}，逐条锁定前后端共享的尺寸规则：
 * 合法 4K {@code 3840x2160} 原样通过；分隔符兼容大写 {@code X} 与首尾空白；空值回落到
 * {@code 1024x1024}；非 16 倍数、单边超过 3840、总像素低于 655360 或高于 8294400、长短边
 * 超过 3:1、格式非法都必须抛 {@link ImageGenerationException} 并带上对应阈值。此外验证
 * 非法尺寸在解析 prompt 与调用 OpenAI 之前就被拒绝，以及默认模型
 * {@code gpt-image-2.5-sunburst} 可被 {@code model.properties} 覆盖。</p>
 *
 * <p>隔离手段：服务以 {@code null} 的 RestTemplate 与空配置构造，校验路径根本不会出网；
 * 模型配置用例写入 JUnit {@code @TempDir} 临时文件。整个类不发起任何真实 HTTP 请求。</p>
 */
class OpenAiImageGenerationServiceTest {

    @TempDir
    Path dir;

    private OpenAiImageGenerationService openAiImageGenerationService;

    @BeforeEach
    void setUp() {
        openAiImageGenerationService = new OpenAiImageGenerationService(null, (ModelProperties.Provider) null);
    }

    @Test
    void normalizeImageSizeAcceptsRecommended4kSize() throws Exception {
        String size = normalizeImageSize("3840x2160");

        assertThat(size).isEqualTo("3840x2160");
    }

    @Test
    void normalizeImageSizeAcceptsUppercaseSeparatorAndWhitespace() throws Exception {
        String size = normalizeImageSize(" 2160X3840 ");

        assertThat(size).isEqualTo("2160x3840");
    }

    @Test
    void normalizeImageSizeDefaultsBlankSize() throws Exception {
        String size = normalizeImageSize("");

        assertThat(size).isEqualTo("1024x1024");
    }

    @Test
    void normalizeImageSizeRejectsNonMultipleOf16() {
        assertThatThrownBy(new org.assertj.core.api.ThrowableAssert.ThrowingCallable() {
            @Override
            public void call() throws Throwable {
                normalizeImageSize("1025x1024");
            }
        }).isInstanceOf(ImageGenerationException.class)
                .hasMessageContaining("16");
    }

    @Test
    void normalizeImageSizeRejectsTooManyPixels() {
        assertThatThrownBy(new org.assertj.core.api.ThrowableAssert.ThrowingCallable() {
            @Override
            public void call() throws Throwable {
                normalizeImageSize("3840x3840");
            }
        }).isInstanceOf(ImageGenerationException.class)
                .hasMessageContaining("8294400");
    }

    @Test
    void normalizeImageSizeRejectsAspectRatioOverThreeToOne() {
        assertThatThrownBy(new org.assertj.core.api.ThrowableAssert.ThrowingCallable() {
            @Override
            public void call() throws Throwable {
                normalizeImageSize("3840x1024");
            }
        }).isInstanceOf(ImageGenerationException.class)
                .hasMessageContaining("3:1");
    }

    @Test
    void normalizeImageSizeRejectsInvalidFormat() {
        assertThatThrownBy(new org.assertj.core.api.ThrowableAssert.ThrowingCallable() {
            @Override
            public void call() throws Throwable {
                normalizeImageSize("1024 x 1024");
            }
        }).isInstanceOf(ImageGenerationException.class)
                .hasMessageContaining("WIDTHxHEIGHT");
    }

    @Test
    void normalizeImageSizeRejectsSideOverLimit() {
        assertThatThrownBy(new org.assertj.core.api.ThrowableAssert.ThrowingCallable() {
            @Override
            public void call() throws Throwable {
                normalizeImageSize("3856x2160");
            }
        }).isInstanceOf(ImageGenerationException.class)
                .hasMessageContaining("3840");
    }

    @Test
    void normalizeImageSizeRejectsTooFewPixels() {
        assertThatThrownBy(new org.assertj.core.api.ThrowableAssert.ThrowingCallable() {
            @Override
            public void call() throws Throwable {
                normalizeImageSize("800x800");
            }
        }).isInstanceOf(ImageGenerationException.class)
                .hasMessageContaining("655360");
    }

    @Test
    void generateRejectsInvalidSizeBeforeResolvingPromptOrCallingOpenAi() {
        ImageGenerationRequest request = new ImageGenerationRequest();
        request.setSize("1025x1024");

        assertThatThrownBy(new org.assertj.core.api.ThrowableAssert.ThrowingCallable() {
            @Override
            public void call() {
                openAiImageGenerationService.generate("direct-prompt", request);
            }
        }).isInstanceOf(ImageGenerationException.class)
                .hasMessageContaining("16");
    }

    @Test
    void defaultsToGptImage25SunburstModel() throws Exception {
        assertThat(readImageModel(openAiImageGenerationService)).isEqualTo("gpt-image-2.5-sunburst");
    }

    @Test
    void readsImageModelFromConfiguration() throws Exception {
        Path config = dir.resolve("model.properties");
        Files.write(config, ("image.base-url=https://images.example/v1\n"
                + "image.api-key=test-only\n"
                + "image.image-model=gpt-image-2.5-flare\n"
                + "image.image-models=gpt-image-2.5-flare,gpt-image-2.5-sunburst\n")
                .getBytes(StandardCharsets.UTF_8));

        OpenAiImageGenerationService service = new OpenAiImageGenerationService(
                null, ModelProperties.load(config).provider("image"));

        assertThat(readImageModel(service)).isEqualTo("gpt-image-2.5-flare");
    }

    /** 读取私有字段 {@code imageModel}，避免为测试放宽生产字段的可见性。 */
    private String readImageModel(OpenAiImageGenerationService service) throws Exception {
        Field field = OpenAiImageGenerationService.class.getDeclaredField("imageModel");
        field.setAccessible(true);
        return (String) field.get(service);
    }

    /**
     * 反射调用私有尺寸归一化方法，并把包装异常还原成业务异常。
     *
     * <p>{@code Method.invoke} 会把 {@link ImageGenerationException} 包进
     * {@link InvocationTargetException}；这里解包后重新抛出，断言才能直接检查类型与消息。</p>
     */
    private String normalizeImageSize(String value) throws Exception {
        Method method = OpenAiImageGenerationService.class.getDeclaredMethod("normalizeImageSize", String.class);
        method.setAccessible(true);
        try {
            return (String) method.invoke(null, value);
        } catch (InvocationTargetException exception) {
            Throwable cause = exception.getCause();
            if (cause instanceof ImageGenerationException) {
                throw (ImageGenerationException) cause;
            }
            throw exception;
        }
    }
}
