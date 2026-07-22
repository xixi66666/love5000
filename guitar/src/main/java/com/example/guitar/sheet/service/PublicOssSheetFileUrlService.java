package com.example.guitar.sheet.service;

import com.example.common.util.OssUtil;
import com.example.guitar.web.GuitarApiException;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

import java.io.UnsupportedEncodingException;
import java.net.URLEncoder;

@Service
public class PublicOssSheetFileUrlService implements SheetFileUrlService {

    private final String publicBaseUrl;
    private final ObjectProvider<OssUtil> ossUtilProvider;

    public PublicOssSheetFileUrlService(@Value("${guitar.oss.public-base-url:}") String publicBaseUrl,
                                        ObjectProvider<OssUtil> ossUtilProvider) {
        this.publicBaseUrl = publicBaseUrl;
        this.ossUtilProvider = ossUtilProvider;
    }

    @Override
    public String getFileUrl(String objectKey) {
        if (objectKey == null || objectKey.trim().isEmpty()) {
            throw unavailable();
        }
        if (publicBaseUrl != null && !publicBaseUrl.trim().isEmpty()) {
            return trimTrailingSlashes(publicBaseUrl.trim()) + "/" + encodeObjectKey(objectKey);
        }
        OssUtil ossUtil = ossUtilProvider.getIfAvailable();
        if (ossUtil == null) {
            throw unavailable();
        }
        return ossUtil.getObjectUrl(objectKey);
    }

    private String encodeObjectKey(String objectKey) {
        String[] segments = objectKey.replace('\\', '/').replaceAll("^/+", "").split("/");
        StringBuilder encoded = new StringBuilder();
        for (String segment : segments) {
            if (segment.isEmpty() || ".".equals(segment) || "..".equals(segment)) {
                throw unavailable();
            }
            if (encoded.length() > 0) {
                encoded.append('/');
            }
            try {
                encoded.append(URLEncoder.encode(segment, "UTF-8").replace("+", "%20"));
            } catch (UnsupportedEncodingException exception) {
                throw new IllegalStateException("UTF-8 is required", exception);
            }
        }
        return encoded.toString();
    }

    private String trimTrailingSlashes(String value) {
        int end = value.length();
        while (end > 0 && value.charAt(end - 1) == '/') {
            end--;
        }
        return value.substring(0, end);
    }

    private GuitarApiException unavailable() {
        return new GuitarApiException(HttpStatus.SERVICE_UNAVAILABLE, "OSS_UNAVAILABLE", "曲谱文件服务暂不可用");
    }
}
