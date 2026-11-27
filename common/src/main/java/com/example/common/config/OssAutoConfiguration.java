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

/**
 * 阿里云 OSS 的自动配置入口。
 *
 * <p>生效条件：classpath 上存在 {@code OSSClientBuilder}，且 {@code love530.oss.enabled=true}。
 * 这里刻意不写 {@code matchIfMissing}：默认关闭，只有显式开启才会创建 {@code OssUtil}，
 * 因此未接入 OSS 的服务启动时不会因为缺少密钥而失败。</p>
 *
 * <p>开启后会校验 endpoint、access-key-id、access-key-secret、bucket-name 四项非空，
 * 缺失时直接抛出异常让启动失败，属于刻意的 fail-fast：避免运行到真正上传时才发现配置残缺。</p>
 *
 * <p>{@code proxyBeanMethods = false} 表示这是纯注册型配置类，Bean 之间不互相调用。</p>
 */
@Configuration(proxyBeanMethods = false)
@ConditionalOnClass(OSSClientBuilder.class)
@EnableConfigurationProperties(OssProperties.class)
@ConditionalOnProperty(prefix = "love530.oss", name = "enabled", havingValue = "true")
public class OssAutoConfiguration {

    /**
     * 校验配置并创建 OSS 工具 Bean。
     *
     * @param ossProperties 已绑定的 {@code love530.oss} 配置
     * @return 使用该配置的 OSS 工具
     * @throws IllegalArgumentException 任一必填项为空时抛出，最终表现为启动失败
     */
    @Bean
    @ConditionalOnMissingBean
    public OssUtil ossUtil(OssProperties ossProperties) {
        validate(ossProperties);
        return new OssUtil(ossProperties);
    }

    /**
     * 校验必填配置，避免带着残缺凭据启动后在运行期才暴露问题。
     *
     * @param ossProperties 待校验的配置
     * @throws IllegalArgumentException 必填项为空白时抛出，消息中会指明具体的配置键
     */
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
