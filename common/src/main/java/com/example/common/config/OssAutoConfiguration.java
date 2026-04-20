package com.example.common.config;

import com.aliyun.oss.OSSClientBuilder;
import com.example.common.util.OssUtil;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.util.Assert;
import org.springframework.util.StringUtils;

@Configuration(proxyBeanMethods = false)
@ConditionalOnClass(OSSClientBuilder.class)
@EnableConfigurationProperties(OssProperties.class)
@ConditionalOnProperty(prefix = "love530.oss", name = "enabled", havingValue = "true")
public class OssAutoConfiguration {

    @Bean
    @ConditionalOnMissingBean
    public OssUtil ossUtil(OssProperties ossProperties) {
        validate(ossProperties);
        return new OssUtil(ossProperties);
    }

    private void validate(OssProperties ossProperties) {
        Assert.isTrue(StringUtils.hasText(ossProperties.getEndpoint()),
                "love530.oss.endpoint must not be blank");
        Assert.isTrue(StringUtils.hasText(ossProperties.getAccessKeyId()),
                "love530.oss.access-key-id must not be blank");
        Assert.isTrue(StringUtils.hasText(ossProperties.getAccessKeySecret()),
                "love530.oss.access-key-secret must not be blank");
        Assert.isTrue(StringUtils.hasText(ossProperties.getBucketName()),
                "love530.oss.bucket-name must not be blank");
    }
}
