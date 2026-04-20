package com.example.common.util;

import com.aliyun.oss.OSS;
import com.aliyun.oss.OSSClientBuilder;
import com.aliyun.oss.model.ObjectMetadata;
import com.aliyun.oss.model.PutObjectRequest;
import com.aliyun.oss.model.PutObjectResult;
import com.example.common.config.OssProperties;
import org.springframework.util.Assert;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.InputStream;
import java.net.URI;
import java.net.URISyntaxException;
import java.net.URLConnection;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;

public class OssUtil {

    private static final DateTimeFormatter DATE_FORMATTER = DateTimeFormatter.ofPattern("yyyy/MM/dd");

    private static final Set<String> IMAGE_EXTENSIONS = new HashSet<String>(
            Arrays.asList("jpg", "jpeg", "png", "gif", "bmp", "webp", "svg"));

    private final OssProperties ossProperties;

    public OssUtil(OssProperties ossProperties) {
        this.ossProperties = ossProperties;
    }

    public OssUploadResult upload(MultipartFile file) {
        return upload(file, ossProperties.getBaseDir());
    }
    public OssUploadResult upload(MultipartFile file, String directory) {
        Assert.notNull(file, "Upload file must not be null");
        if (file.isEmpty()) {
            throw new IllegalArgumentException("Upload file must not be empty");
        }

        try (InputStream inputStream = file.getInputStream()) {
            return upload(inputStream, file.getSize(), file.getOriginalFilename(), file.getContentType(), directory);
        } catch (IOException e) {
            throw new IllegalStateException("Failed to read upload file", e);
        }
    }

    public OssUploadResult upload(InputStream inputStream, long contentLength, String originalFilename) {
        return upload(inputStream, contentLength, originalFilename, null, ossProperties.getBaseDir());
    }

    public OssUploadResult upload(InputStream inputStream, long contentLength, String originalFilename,
                                  String contentType, String directory) {
        Assert.notNull(inputStream, "Upload stream must not be null");

        String objectKey = buildObjectKey(directory, originalFilename);
        ObjectMetadata metadata = buildMetadata(contentLength, originalFilename, contentType);

        OSS ossClient = createClient();
        try {
            PutObjectRequest putObjectRequest =
                    new PutObjectRequest(ossProperties.getBucketName(), objectKey, inputStream, metadata);
            PutObjectResult result = ossClient.putObject(putObjectRequest);
            return new OssUploadResult(
                    ossProperties.getBucketName(),
                    objectKey,
                    getObjectUrl(objectKey),
                    result.getETag(),
                    originalFilename,
                    contentLength
            );
        } catch (Exception e) {
            throw new IllegalStateException("Failed to upload file to OSS", e);
        } finally {
            ossClient.shutdown();
        }
    }

    public boolean exists(String objectKeyOrUrl) {
        String objectKey = extractObjectKey(objectKeyOrUrl);
        OSS ossClient = createClient();
        try {
            return ossClient.doesObjectExist(ossProperties.getBucketName(), objectKey);
        } catch (Exception e) {
            throw new IllegalStateException("Failed to check OSS object existence", e);
        } finally {
            ossClient.shutdown();
        }
    }

    public void delete(String objectKeyOrUrl) {
        String objectKey = extractObjectKey(objectKeyOrUrl);
        OSS ossClient = createClient();
        try {
            if (ossClient.doesObjectExist(ossProperties.getBucketName(), objectKey)) {
                ossClient.deleteObject(ossProperties.getBucketName(), objectKey);
            }
        } catch (Exception e) {
            throw new IllegalStateException("Failed to delete OSS object", e);
        } finally {
            ossClient.shutdown();
        }
    }

    public String getObjectUrl(String objectKeyOrUrl) {
        String objectKey = extractObjectKey(objectKeyOrUrl);
        if (StringUtils.hasText(ossProperties.getUrlPrefix())) {
            return joinUrl(trimTrailingSlash(ossProperties.getUrlPrefix().trim()), objectKey);
        }

        String endpoint = trimTrailingSlash(ossProperties.getEndpoint().trim());
        if (endpoint.startsWith("http://") || endpoint.startsWith("https://")) {
            return joinUrl(endpoint.replace("://", "://" + ossProperties.getBucketName() + "."), objectKey);
        }

        String schema = ossProperties.isUseHttps() ? "https://" : "http://";
        return joinUrl(schema + ossProperties.getBucketName() + "." + endpoint, objectKey);
    }

    public String extractObjectKey(String objectKeyOrUrl) {
        if (!StringUtils.hasText(objectKeyOrUrl)) {
            throw new IllegalArgumentException("OSS object key must not be blank");
        }

        String candidate = objectKeyOrUrl.trim();
        if (StringUtils.hasText(ossProperties.getUrlPrefix())) {
            String urlPrefix = trimTrailingSlash(ossProperties.getUrlPrefix().trim());
            if (candidate.startsWith(urlPrefix)) {
                return sanitizeObjectKey(candidate.substring(urlPrefix.length()));
            }
        }

        if (candidate.startsWith("http://") || candidate.startsWith("https://")) {
            try {
                return sanitizeObjectKey(new URI(candidate).getPath());
            } catch (URISyntaxException e) {
                throw new IllegalArgumentException("Illegal OSS url: " + candidate, e);
            }
        }

        return sanitizeObjectKey(candidate.replace("\\", "/"));
    }

    private OSS createClient() {
        return new OSSClientBuilder().build(
                ossProperties.getEndpoint(),
                ossProperties.getAccessKeyId(),
                ossProperties.getAccessKeySecret()
        );
    }

    private String buildObjectKey(String directory, String originalFilename) {
        String normalizedDirectory = normalizeDirectory(directory);
        String datePath = LocalDate.now().format(DATE_FORMATTER);
        String extension = getExtension(originalFilename);

        StringBuilder objectKeyBuilder = new StringBuilder();
        if (StringUtils.hasText(normalizedDirectory)) {
            objectKeyBuilder.append(normalizedDirectory).append("/");
        }
        objectKeyBuilder.append(datePath).append("/").append(UUID.randomUUID());
        if (StringUtils.hasText(extension)) {
            objectKeyBuilder.append(".").append(extension);
        }
        return objectKeyBuilder.toString();
    }

    private ObjectMetadata buildMetadata(long contentLength, String originalFilename, String contentType) {
        ObjectMetadata metadata = new ObjectMetadata();
        if (contentLength >= 0) {
            metadata.setContentLength(contentLength);
        }
        metadata.setContentType(resolveContentType(originalFilename, contentType));
        metadata.setCacheControl("no-cache");
        return metadata;
    }

    private String resolveContentType(String originalFilename, String contentType) {
        if (StringUtils.hasText(contentType)) {
            return contentType;
        }

        if (StringUtils.hasText(originalFilename)) {
            String detectedContentType = URLConnection.getFileNameMap().getContentTypeFor(originalFilename);
            if (StringUtils.hasText(detectedContentType)) {
                return detectedContentType;
            }

            String extension = getExtension(originalFilename);
            if (IMAGE_EXTENSIONS.contains(extension)) {
                if ("svg".equals(extension)) {
                    return "image/svg+xml";
                }
                return "image/" + ("jpg".equals(extension) ? "jpeg" : extension);
            }
        }

        return "application/octet-stream";
    }

    private String normalizeDirectory(String directory) {
        String finalDirectory = StringUtils.hasText(directory) ? directory : ossProperties.getBaseDir();
        if (!StringUtils.hasText(finalDirectory)) {
            return "";
        }
        return stripLeadingSlash(trimTrailingSlash(finalDirectory.trim().replace("\\", "/")));
    }

    private String getExtension(String originalFilename) {
        if (!StringUtils.hasText(originalFilename) || !originalFilename.contains(".")) {
            return "";
        }
        return originalFilename.substring(originalFilename.lastIndexOf('.') + 1).toLowerCase(Locale.ROOT);
    }

    private String joinUrl(String prefix, String objectKey) {
        return trimTrailingSlash(prefix) + "/" + stripLeadingSlash(objectKey);
    }

    private String trimTrailingSlash(String value) {
        String result = value;
        while (result.endsWith("/")) {
            result = result.substring(0, result.length() - 1);
        }
        return result;
    }

    private String stripLeadingSlash(String value) {
        if (value == null) {
            return "";
        }

        String result = value;
        while (result.startsWith("/")) {
            result = result.substring(1);
        }
        System.out.println("hahahahahahahsdaaiubhdabuisd ");
        return result;
    }

    private String sanitizeObjectKey(String value) {
        String normalized = stripLeadingSlash(value);
        int queryIndex = normalized.indexOf('?');
        if (queryIndex >= 0) {
            normalized = normalized.substring(0, queryIndex);
        }
        int fragmentIndex = normalized.indexOf('#');
        if (fragmentIndex >= 0) {
            normalized = normalized.substring(0, fragmentIndex);
        }
        return normalized;
    }
}
