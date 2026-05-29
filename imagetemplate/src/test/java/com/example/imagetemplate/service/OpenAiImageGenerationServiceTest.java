package com.example.imagetemplate.service;

import com.example.imagetemplate.dto.ImageGenerationRequest;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.core.env.StandardEnvironment;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class OpenAiImageGenerationServiceTest {

    private OpenAiImageGenerationService openAiImageGenerationService;

    @BeforeEach
    void setUp() {
        openAiImageGenerationService = new OpenAiImageGenerationService(null, new StandardEnvironment());
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
                openAiImageGenerationService.generate("direct-prompt", request, "sk-test");
            }
        }).isInstanceOf(ImageGenerationException.class)
                .hasMessageContaining("16");
    }

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
