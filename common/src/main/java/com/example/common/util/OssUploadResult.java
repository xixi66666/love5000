package com.example.common.util;

public class OssUploadResult {

    private String bucketName;

    private String objectKey;

    private String url;

    private String etag;

    private String originalFilename;

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
