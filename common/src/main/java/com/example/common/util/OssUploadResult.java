package com.example.common.util;

/**
 * OSS 上传成功后的结果快照。
 *
 * <p>同时给出对象键与访问地址：{@code objectKey} 用于后续删除或幂等补偿，
 * {@code url} 由 {@code OssUtil#getObjectUrl} 按当前配置拼接。两者不保证可以互相推导
 * （配置了自定义 {@code url-prefix} 时尤其明显），所以调用方应持久化对象键，而不是只存 URL。</p>
 */
public class OssUploadResult {

    private String bucketName;

    /** 对象键，即 Bucket 内的完整路径；删除与存在性判断都应使用它。 */
    private String objectKey;

    private String url;

    /** OSS 返回的 ETag，可用于校验上传内容是否完整。 */
    private String etag;

    private String originalFilename;

    /** 上传内容的字节数，直接回填调用方传入的长度，工具类本身不做二次校验。 */
    private long size;

    public OssUploadResult() {
    }

    public OssUploadResult(String bucketName, String objectKey, String url, String etag,
                           String originalFilename, long size) {
        this.bucketName = bucketName;
        this.objectKey = objectKey;
        this.url = url;
        this.etag = etag;
        this.originalFilename = originalFilename;
        this.size = size;
    }

    public String getBucketName() {
        return bucketName;
    }

    public void setBucketName(String bucketName) {
        this.bucketName = bucketName;
    }

    public String getObjectKey() {
        return objectKey;
    }

    public void setObjectKey(String objectKey) {
        this.objectKey = objectKey;
    }

    public String getUrl() {
        return url;
    }

    public void setUrl(String url) {
        this.url = url;
    }

    public String getEtag() {
        return etag;
    }

    public void setEtag(String etag) {
        this.etag = etag;
    }

    public String getOriginalFilename() {
        return originalFilename;
    }

    public void setOriginalFilename(String originalFilename) {
        this.originalFilename = originalFilename;
    }

    public long getSize() {
        return size;
    }

    public void setSize(long size) {
        this.size = size;
    }
}
