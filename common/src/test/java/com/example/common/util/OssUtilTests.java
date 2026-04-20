package com.example.common.util;

import com.example.common.config.OssProperties;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class OssUtilTests {

    @Test
    void shouldBuildUrlWithCustomDomain() {
        OssProperties ossProperties = new OssProperties();
        ossProperties.setEndpoint("oss-cn-hangzhou.aliyuncs.com");
        ossProperties.setAccessKeyId("test-id");
        ossProperties.setAccessKeySecret("test-secret");
        ossProperties.setBucketName("love530");
        ossProperties.setUrlPrefix("https://cdn.love530.com/files");

        OssUtil ossUtil = new OssUtil(ossProperties);

        assertEquals("https://cdn.love530.com/files/photo/test.png",
                ossUtil.getObjectUrl("photo/test.png"));
    }

    @Test
    void shouldExtractObjectKeyFromUrl() {
        OssProperties ossProperties = new OssProperties();
        ossProperties.setEndpoint("oss-cn-hangzhou.aliyuncs.com");
        ossProperties.setAccessKeyId("test-id");
        ossProperties.setAccessKeySecret("test-secret");
        ossProperties.setBucketName("love530");
        ossProperties.setUrlPrefix("https://cdn.love530.com/files");

        OssUtil ossUtil = new OssUtil(ossProperties);

        assertEquals("photo/test.png",
                ossUtil.extractObjectKey("https://cdn.love530.com/files/photo/test.png?x-oss-process=image/resize"));
    }
}
