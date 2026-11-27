package com.example.common.util;

import com.example.common.config.OssProperties;
import org.junit.jupiter.api.Test;

import java.io.ByteArrayInputStream;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * {@code OssUtil} 的地址拼接与对象键校验测试。
 *
 * <p>全部用例只做纯计算断言，不连接阿里云 OSS，也不使用真实 AccessKey：
 * 覆盖自定义 CDN 前缀拼接、带 query 参数的 URL 反解，以及预声明对象键的格式校验
 * （以斜杠开头的路径、路径穿越和带 query 的键都会被拒绝）。</p>
 */
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

    @Test
    void shouldValidatePredeclaredObjectKeysWithoutCallingOss() {
        OssProperties ossProperties = new OssProperties();
        OssUtil ossUtil = new OssUtil(ossProperties);

        assertEquals("love530/guitar/sheets/uuid/pdf/sheet.pdf",
                ossUtil.validateObjectKey("love530/guitar/sheets/uuid/pdf/sheet.pdf"));
        org.junit.jupiter.api.Assertions.assertThrows(IllegalArgumentException.class,
                () -> ossUtil.validateObjectKey("/love530/guitar/sheets/uuid/pdf/sheet.pdf"));
        org.junit.jupiter.api.Assertions.assertThrows(IllegalArgumentException.class,
                () -> ossUtil.validateObjectKey("love530/guitar/sheets/uuid/../sheet.pdf"));
        org.junit.jupiter.api.Assertions.assertThrows(IllegalArgumentException.class,
                () -> ossUtil.validateObjectKey("love530/guitar/sheets/uuid/sheet.pdf?download=1"));
        org.junit.jupiter.api.Assertions.assertThrows(IllegalArgumentException.class,
                () -> ossUtil.uploadWithObjectKey(new ByteArrayInputStream(new byte[]{1}), 1L,
                        "love530/guitar/sheets/uuid/../sheet.pdf", "sheet.pdf", "application/pdf"));
    }
}
