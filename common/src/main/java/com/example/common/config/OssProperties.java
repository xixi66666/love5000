package com.example.common.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * {@code love530.oss} 前缀下的对象存储配置。
 *
 * <p>{@code enabled} 默认为 {@code false}，此时 {@code OssAutoConfiguration} 不会创建
 * {@code OssUtil}；依赖 OSS 的服务必须自行容错（判空注入或改用 {@code ObjectProvider}），
 * 否则缺少 Bean 会在启动时直接失败。</p>
 *
 * <p>访问地址有两种来源：配置了 {@code url-prefix} 时以它为前缀（通常指向 CDN 或自有域名），
 * 否则按「bucket 名 + endpoint」拼出默认域名，协议由 {@code use-https} 决定。</p>
 */
@ConfigurationProperties(prefix = "love530.oss")
public class OssProperties {

    /** 是否启用 OSS；默认关闭，只有显式开启才会装配 {@code OssUtil}。 */
    private boolean enabled;

    /** 服务端点，例如 {@code oss-cn-beijing.aliyuncs.com}；允许带 http 或 https 协议前缀。 */
    private String endpoint;

    /** AccessKey ID，建议只通过环境变量注入，不要提交到仓库。 */
    private String accessKeyId;

    /** AccessKey Secret，与 ID 成对使用；同样只应通过环境变量或本地私有文件注入。 */
    private String accessKeySecret;

    /** 目标 Bucket 名称；拼接默认访问域名时它同时充当主机名前缀。 */
    private String bucketName;

    /** 自定义访问前缀（CDN 或自有域名）；为空时按 bucket 拼接默认域名，结尾多余斜杠会被忽略。 */
    private String urlPrefix;

    /** 默认上传目录前缀，默认 {@code love530}；调用方未指定目录时对象键会以此开头。 */
    private String baseDir = "love530";

    /** 拼接默认域名时是否使用 HTTPS，默认开启；仅在未配置 url-prefix 且 endpoint 不带协议时生效。 */
    private boolean useHttps = true;

    public boolean isEnabled() {
        return enabled;
    }

    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
    }

    public String getEndpoint() {
        return endpoint;
    }

    public void setEndpoint(String endpoint) {
        this.endpoint = endpoint;
    }

    public String getAccessKeyId() {
        return accessKeyId;
    }

    public void setAccessKeyId(String accessKeyId) {
        this.accessKeyId = accessKeyId;
    }

    public String getAccessKeySecret() {
        return accessKeySecret;
    }

    public void setAccessKeySecret(String accessKeySecret) {
        this.accessKeySecret = accessKeySecret;
    }

    public String getBucketName() {
        return bucketName;
    }

    public void setBucketName(String bucketName) {
        this.bucketName = bucketName;
    }

    public String getUrlPrefix() {
        return urlPrefix;
    }

    public void setUrlPrefix(String urlPrefix) {
        this.urlPrefix = urlPrefix;
    }

    public String getBaseDir() {
        return baseDir;
    }

    public void setBaseDir(String baseDir) {
        this.baseDir = baseDir;
    }

    public boolean isUseHttps() {
        return useHttps;
    }

    public void setUseHttps(boolean useHttps) {
        this.useHttps = useHttps;
    }
}
