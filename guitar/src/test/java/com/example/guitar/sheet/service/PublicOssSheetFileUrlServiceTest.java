package com.example.guitar.sheet.service;

import com.example.common.util.OssUtil;
import com.example.guitar.web.GuitarApiException;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.ObjectProvider;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class PublicOssSheetFileUrlServiceTest {

    @Test
    void configuredPublicBaseUrlEncodesEachObjectKeyPathSegment() {
        PublicOssSheetFileUrlService service = new PublicOssSheetFileUrlService(
                "https://cdn.example/guitar/", ossUtilProvider(null));

        assertThat(service.getFileUrl("sheets/9/a b#1.pdf"))
                .isEqualTo("https://cdn.example/guitar/sheets/9/a%20b%231.pdf");
    }

    @Test
    void ossFallbackIsUsedWhenPublicBaseUrlIsNotConfigured() {
        OssUtil ossUtil = mock(OssUtil.class);
        when(ossUtil.getObjectUrl("sheets/9/tab.pdf")).thenReturn("https://oss.example/tab.pdf");
        PublicOssSheetFileUrlService service = new PublicOssSheetFileUrlService(" ", ossUtilProvider(ossUtil));

        assertThat(service.getFileUrl("sheets/9/tab.pdf")).isEqualTo("https://oss.example/tab.pdf");
    }

    @Test
    void missingUrlConfigurationProducesStableOssUnavailableError() {
        PublicOssSheetFileUrlService service = new PublicOssSheetFileUrlService(null, ossUtilProvider(null));

        assertThatThrownBy(() -> service.getFileUrl("sheets/9/tab.pdf"))
                .isInstanceOfSatisfying(GuitarApiException.class,
                        exception -> assertThat(exception.getCode()).isEqualTo("OSS_UNAVAILABLE"));
    }

    @SuppressWarnings("unchecked")
    private ObjectProvider<OssUtil> ossUtilProvider(OssUtil ossUtil) {
        ObjectProvider<OssUtil> provider = mock(ObjectProvider.class);
        when(provider.getIfAvailable()).thenReturn(ossUtil);
        return provider;
    }
}
