package com.ycxandwuqian.love.service;

import com.example.common.util.OssUploadResult;
import com.example.common.util.OssUtil;
import com.ycxandwuqian.love.dao.GuitarVideoDao;
import com.ycxandwuqian.love.model.GuitarVideoRecord;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.dao.DataAccessException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

@Service
public class GuitarVideoServiceImpl implements GuitarVideoService {

    private static final String VIDEO_DIRECTORY = "love530/lovestory/videos";

    private static final String COVER_DIRECTORY = "love530/lovestory/videos/covers";

    private static final int DISPLAY_STATUS = 1;

    private static final DateTimeFormatter TIME_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private static final Set<String> VIDEO_EXTENSIONS =
            new HashSet<String>(Arrays.asList("mp4", "webm", "mov"));

    private static final Set<String> IMAGE_EXTENSIONS =
            new HashSet<String>(Arrays.asList("jpg", "jpeg", "png", "webp"));

    private final ObjectProvider<OssUtil> ossUtilProvider;

    private final GuitarVideoDao guitarVideoDao;

    public GuitarVideoServiceImpl(ObjectProvider<OssUtil> ossUtilProvider, GuitarVideoDao guitarVideoDao) {
        this.ossUtilProvider = ossUtilProvider;
        this.guitarVideoDao = guitarVideoDao;
    }

    @Override
    public Map<String, Object> listVideos() {
        Map<String, Object> response = new HashMap<String, Object>();
        try {
            List<Map<String, Object>> videos = guitarVideoDao.findVisible().stream()
                    .map(this::buildVideoResponse)
                    .collect(Collectors.toList());
            response.put("success", true);
            response.put("videos", videos);
        } catch (DataAccessException e) {
            response.put("success", false);
            response.put("message", "Failed to load videos: " + e.getMessage());
            response.put("videos", Collections.emptyList());
        }
        return response;
    }

    @Override
    @Transactional
    public Map<String, Object> uploadVideo(MultipartFile file, MultipartFile cover, String title,
                                           String description, String tag, Integer sortOrder) {
        Map<String, Object> response = new HashMap<String, Object>();

        String normalizedTitle = normalizeText(title);
        if (!StringUtils.hasText(normalizedTitle)) {
            response.put("success", false);
            response.put("message", "Video title must not be blank");
            return response;
        }

        if (file == null || file.isEmpty()) {
            response.put("success", false);
            response.put("message", "Please select a video file");
            return response;
        }

        if (!hasAllowedExtension(file.getOriginalFilename(), VIDEO_EXTENSIONS)) {
            response.put("success", false);
            response.put("message", "Only mp4, webm and mov videos are supported");
            return response;
        }

        if (cover != null && !cover.isEmpty() && !hasAllowedExtension(cover.getOriginalFilename(), IMAGE_EXTENSIONS)) {
            response.put("success", false);
            response.put("message", "Only jpg, jpeg, png and webp covers are supported");
            return response;
        }

        OssUtil ossUtil = ossUtilProvider.getIfAvailable();
        if (ossUtil == null) {
            response.put("success", false);
            response.put("message", "OSS is not configured");
            return response;
        }

        try {
            OssUploadResult videoUpload = ossUtil.upload(file, VIDEO_DIRECTORY);
            String coverUrl = "";
            if (cover != null && !cover.isEmpty()) {
                coverUrl = ossUtil.upload(cover, COVER_DIRECTORY).getUrl();
            }

            GuitarVideoRecord record = new GuitarVideoRecord();
            record.setTitle(truncate(normalizedTitle, 100));
            record.setDescription(truncate(normalizeText(description), 500));
            record.setTag(truncate(normalizeText(tag), 50));
            record.setVideoUrl(videoUpload.getUrl());
            record.setCoverUrl(coverUrl);
            record.setSortOrder(sortOrder == null ? 0 : sortOrder);
            record.setStatus(DISPLAY_STATUS);
            record.setCreateTime(LocalDateTime.now());
            record.setUpdateTime(record.getCreateTime());
            guitarVideoDao.insert(record);

            response.put("success", true);
            response.put("message", "Upload succeeded");
            response.put("video", buildVideoResponse(record));
        } catch (IllegalArgumentException | IllegalStateException | DataAccessException e) {
            response.put("success", false);
            response.put("message", "Upload failed: " + e.getMessage());
        }

        return response;
    }

    @Override
    @Transactional
    public Map<String, Object> deleteVideo(Long id) {
        Map<String, Object> response = new HashMap<String, Object>();
        try {
            GuitarVideoRecord record = guitarVideoDao.findById(id);
            if (record == null) {
                response.put("success", false);
                response.put("message", "Video not found");
                return response;
            }

            OssUtil ossUtil = ossUtilProvider.getIfAvailable();
            if (ossUtil != null) {
                deleteQuietly(ossUtil, record.getVideoUrl());
                deleteQuietly(ossUtil, record.getCoverUrl());
            }

            if (guitarVideoDao.hideById(id) <= 0) {
                response.put("success", false);
                response.put("message", "Failed to delete video record");
                return response;
            }

            response.put("success", true);
            response.put("message", "Video deleted");
            response.put("id", id);
        } catch (IllegalArgumentException | IllegalStateException | DataAccessException e) {
            response.put("success", false);
            response.put("message", "Delete failed: " + e.getMessage());
        }
        return response;
    }

    @Override
    @Transactional
    public Map<String, Object> uploadCover(Long id, MultipartFile cover) {
        Map<String, Object> response = new HashMap<String, Object>();
        if (cover == null || cover.isEmpty()) {
            response.put("success", false);
            response.put("message", "Please select a cover image");
            return response;
        }
        if (!hasAllowedExtension(cover.getOriginalFilename(), IMAGE_EXTENSIONS)) {
            response.put("success", false);
            response.put("message", "Only jpg, jpeg, png and webp covers are supported");
            return response;
        }

        try {
            GuitarVideoRecord record = guitarVideoDao.findById(id);
            if (record == null) {
                response.put("success", false);
                response.put("message", "Video not found");
                return response;
            }

            OssUtil ossUtil = ossUtilProvider.getIfAvailable();
            if (ossUtil == null) {
                response.put("success", false);
                response.put("message", "OSS is not configured");
                return response;
            }

            OssUploadResult coverUpload = ossUtil.upload(cover, COVER_DIRECTORY);
            record.setCoverUrl(coverUpload.getUrl());
            if (guitarVideoDao.updateCoverUrl(id, coverUpload.getUrl()) <= 0) {
                response.put("success", false);
                response.put("message", "Failed to update video cover");
                return response;
            }

            response.put("success", true);
            response.put("message", "Cover uploaded");
            response.put("video", buildVideoResponse(record));
        } catch (IllegalArgumentException | IllegalStateException | DataAccessException e) {
            response.put("success", false);
            response.put("message", "Cover upload failed: " + e.getMessage());
        }

        return response;
    }

    private Map<String, Object> buildVideoResponse(GuitarVideoRecord record) {
        Map<String, Object> video = new LinkedHashMap<String, Object>();
        video.put("id", record.getId());
        video.put("title", record.getTitle());
        video.put("description", emptyIfNull(record.getDescription()));
        video.put("tag", emptyIfNull(record.getTag()));
        video.put("videoUrl", resolveMediaUrl(record.getVideoUrl()));
        video.put("coverUrl", resolveMediaUrl(record.getCoverUrl()));
        video.put("durationSeconds", record.getDurationSeconds());
        video.put("sortOrder", record.getSortOrder());
        if (record.getCreateTime() != null) {
            video.put("createTime", TIME_FORMATTER.format(record.getCreateTime()));
        }
        return video;
    }

    private String resolveMediaUrl(String urlOrObjectKey) {
        if (!StringUtils.hasText(urlOrObjectKey)) {
            return "";
        }
        if (urlOrObjectKey.startsWith("http://") || urlOrObjectKey.startsWith("https://")) {
            return urlOrObjectKey;
        }
        OssUtil ossUtil = ossUtilProvider.getIfAvailable();
        if (ossUtil == null) {
            return urlOrObjectKey;
        }
        return ossUtil.getObjectUrl(urlOrObjectKey);
    }

    private void deleteQuietly(OssUtil ossUtil, String urlOrObjectKey) {
        if (StringUtils.hasText(urlOrObjectKey)) {
            ossUtil.delete(urlOrObjectKey);
        }
    }

    private boolean hasAllowedExtension(String originalFilename, Set<String> allowedExtensions) {
        String extension = getExtension(originalFilename);
        return allowedExtensions.contains(extension);
    }

    private String getExtension(String originalFilename) {
        if (!StringUtils.hasText(originalFilename) || !originalFilename.contains(".")) {
            return "";
        }
        return originalFilename.substring(originalFilename.lastIndexOf('.') + 1).toLowerCase(Locale.ROOT);
    }

    private String normalizeText(String value) {
        return StringUtils.hasText(value) ? value.trim() : "";
    }

    private String truncate(String value, int maxLength) {
        if (value == null || value.length() <= maxLength) {
            return value;
        }
        return value.substring(0, maxLength);
    }

    private String emptyIfNull(String value) {
        return value == null ? "" : value;
    }
}
