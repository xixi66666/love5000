package com.ycxandwuqian.love.service;

import com.example.common.util.OssUploadResult;
import com.example.common.util.OssUtil;
import com.ycxandwuqian.love.dao.PhotoDao;
import com.ycxandwuqian.love.model.PhotoRecord;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.dao.DataAccessException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.interceptor.TransactionAspectSupport;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;

import java.time.LocalDate;
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
import java.util.UUID;
import java.util.stream.Collectors;

@Service
public class PhotoServiceImpl implements PhotoService {

    private static final Logger LOGGER = LoggerFactory.getLogger(PhotoServiceImpl.class);

    private static final Set<String> ALLOWED_CATEGORIES =
            new HashSet<String>(Arrays.asList("cat", "girl", "us"));

    private static final DateTimeFormatter TIME_FORMATTER =
            DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private static final DateTimeFormatter OBJECT_KEY_DATE_FORMATTER =
            DateTimeFormatter.ofPattern("yyyy/MM/dd");

    private static final String PHOTO_DIRECTORY = "love530/lovestory/photos";

    private static final int MAX_LOG_VALUE_LENGTH = 200;

    private final ObjectProvider<OssUtil> ossUtilProvider;

    private final PhotoDao photoDao;

    public PhotoServiceImpl(ObjectProvider<OssUtil> ossUtilProvider, PhotoDao photoDao) {
        this.ossUtilProvider = ossUtilProvider;
        this.photoDao = photoDao;
    }

    @Override
    public Map<String, Object> uploadPhoto(MultipartFile file, String category, String description) {
        Map<String, Object> response = new HashMap<String, Object>();

        if (file == null || file.isEmpty()) {
            return failure(response, "Please select a file");
        }

        String originalFilename = file.getOriginalFilename();
        if (!isSupportedImage(originalFilename)) {
            return failure(response, "Only jpg, jpeg, png, gif and webp images are supported");
        }

        String normalizedCategory = normalizeCategory(category);
        if (!ALLOWED_CATEGORIES.contains(normalizedCategory)) {
            return failure(response, "Unsupported photo category");
        }

        OssUtil ossUtil = ossUtilProvider.getIfAvailable();
        if (ossUtil == null) {
            return failure(response, "OSS is not configured");
        }

        String sanitizedDescription = StringUtils.hasText(description) ? description.trim() : "";
        String objectKey = buildPhotoObjectKey(normalizedCategory, originalFilename);
        boolean uploadAttempted = false;
        boolean persisted = false;

        try {
            // 先确定对象键，再调用 OSS；即使 OSS 接受对象后本地响应异常，也能按该键补偿。
            uploadAttempted = true;
            OssUploadResult uploadResult =
                    ossUtil.uploadWithObjectKey(file, objectKey, file.getContentType());
            if (uploadResult == null
                    || !objectKey.equals(trimToEmpty(uploadResult.getObjectKey()))) {
                throw new IllegalStateException("Uploaded object key could not be confirmed");
            }

            String url = resolveUploadUrl(ossUtil, uploadResult, objectKey);
            PhotoRecord photoRecord = new PhotoRecord();
            photoRecord.setPath(objectKey);
            photoRecord.setType(normalizedCategory);
            photoRecord.setCreateTime(LocalDateTime.now());

            if (photoDao.insert(photoRecord) <= 0) {
                throw new IllegalStateException("Failed to save photo record");
            }
            persisted = true;

            response.put("success", true);
            response.put("message", "Upload succeeded");
            response.put("url", url);
            response.put("photo", buildPhotoResponse(
                    url, normalizedCategory, sanitizedDescription, photoRecord));
            return response;
        } catch (RuntimeException uploadFailure) {
            if (uploadAttempted && !persisted) {
                compensateUploadedObject(ossUtil, objectKey, uploadFailure);
            }
            return failure(response, "Upload failed: " + failureMessage(uploadFailure));
        }
    }

    @Override
    public Map<String, Object> listPhotos() {
        Map<String, Object> response = new HashMap<String, Object>();

        try {
            List<Map<String, Object>> photos = photoDao.findAll().stream()
                    .map(photoRecord -> buildPhotoResponse(
                            resolvePhotoUrl(photoRecord.getPath()),
                            photoRecord.getType(),
                            buildDefaultDescription(photoRecord),
                            photoRecord))
                    .collect(Collectors.toList());
            response.put("success", true);
            response.put("photos", photos);
        } catch (DataAccessException e) {
            response.put("success", false);
            response.put("message", "Failed to load photos: " + failureMessage(e));
            response.put("photos", Collections.emptyList());
        }

        return response;
    }

    @Override
    @Transactional
    public Map<String, Object> deletePhoto(Long id) {
        Map<String, Object> response = new HashMap<String, Object>();

        try {
            PhotoRecord photoRecord = photoDao.findById(id);
            if (photoRecord == null) {
                return failure(response, "Photo not found");
            }

            // 先确认数据库记录删除成功，避免 OSS 已删除但照片记录仍留在列表里。
            if (photoDao.deleteById(id) <= 0) {
                if (photoDao.findById(id) == null) {
                    // 并发或重复的删除请求：记录已经被另一请求删除，按目标状态返回成功。
                    return deleted(response, id);
                }
                return failure(response, "Failed to delete photo record");
            }

            OssUtil ossUtil = ossUtilProvider.getIfAvailable();
            if (ossUtil != null && StringUtils.hasText(photoRecord.getPath())) {
                ossUtil.delete(photoRecord.getPath());
            }

            return deleted(response, id);
        } catch (RuntimeException deleteFailure) {
            // deletePhoto 由 Spring 事务代理调用；OSS 清理失败时回滚刚完成的数据库删除，
            // 让记录和对象保持同一状态，而不是留下指向已删除对象的照片记录。
            markRollbackOnlyIfActive();
            return failure(response, "Delete failed: " + failureMessage(deleteFailure));
        }
    }

    private Map<String, Object> failure(Map<String, Object> response, String message) {
        response.put("success", false);
        response.put("message", message);
        return response;
    }

    private Map<String, Object> deleted(Map<String, Object> response, Long id) {
        response.put("success", true);
        response.put("message", "Photo deleted");
        response.put("id", id);
        return response;
    }

    private String buildPhotoObjectKey(String category, String originalFilename) {
        StringBuilder objectKey = new StringBuilder(PHOTO_DIRECTORY)
                .append('/')
                .append(category)
                .append('/')
                .append(LocalDate.now().format(OBJECT_KEY_DATE_FORMATTER))
                .append('/')
                .append(UUID.randomUUID());
        String extension = getExtension(originalFilename);
        if (StringUtils.hasText(extension)) {
            objectKey.append('.').append(extension);
        }
        return objectKey.toString();
    }

    private String resolveUploadUrl(OssUtil ossUtil, OssUploadResult uploadResult, String objectKey) {
        if (uploadResult != null && StringUtils.hasText(uploadResult.getUrl())) {
            return uploadResult.getUrl();
        }
        String url = ossUtil.getObjectUrl(objectKey);
        return url == null ? "" : url;
    }

    private void compensateUploadedObject(OssUtil ossUtil, String objectKey, RuntimeException originalFailure) {
        if (!StringUtils.hasText(objectKey)) {
            return;
        }
        try {
            ossUtil.delete(objectKey);
        } catch (RuntimeException cleanupFailure) {
            if (cleanupFailure != originalFailure) {
                originalFailure.addSuppressed(cleanupFailure);
            }
            LOGGER.warn("Failed to remove orphaned photo object, objectKey="
                    + sanitizeForLog(objectKey), cleanupFailure);
        }
    }

    private void markRollbackOnlyIfActive() {
        if (TransactionSynchronizationManager.isActualTransactionActive()) {
            TransactionAspectSupport.currentTransactionStatus().setRollbackOnly();
        }
    }

    private boolean isSupportedImage(String originalFilename) {
        if (!StringUtils.hasText(originalFilename)) {
            return false;
        }

        String lowerCaseName = originalFilename.toLowerCase(Locale.ROOT);
        return lowerCaseName.matches(".*\\.(jpg|jpeg|png|gif|webp)$");
    }

    private String normalizeCategory(String category) {
        if (!StringUtils.hasText(category)) {
            return "";
        }
        return category.trim().toLowerCase(Locale.ROOT);
    }

    private String getExtension(String originalFilename) {
        if (!StringUtils.hasText(originalFilename) || !originalFilename.contains(".")) {
            return "";
        }
        return originalFilename.substring(originalFilename.lastIndexOf('.') + 1)
                .toLowerCase(Locale.ROOT);
    }

    private String resolvePhotoUrl(String path) {
        if (!StringUtils.hasText(path)) {
            return "";
        }

        if (path.startsWith("http://") || path.startsWith("https://")) {
            return path;
        }

        OssUtil ossUtil = ossUtilProvider.getIfAvailable();
        if (ossUtil == null) {
            return path;
        }
        return ossUtil.getObjectUrl(path);
    }

    private String buildDefaultDescription(PhotoRecord photoRecord) {
        String categoryLabel = categoryLabel(photoRecord.getType());
        if (photoRecord.getCreateTime() == null) {
            return categoryLabel;
        }
        return categoryLabel + " · " + TIME_FORMATTER.format(photoRecord.getCreateTime());
    }

    private Map<String, Object> buildPhotoResponse(String url, String category,
                                                   String description, PhotoRecord photoRecord) {
        Map<String, Object> photo = new LinkedHashMap<String, Object>();
        if (photoRecord != null) {
            photo.put("id", photoRecord.getId());
            if (photoRecord.getCreateTime() != null) {
                photo.put("createTime", TIME_FORMATTER.format(photoRecord.getCreateTime()));
            }
        }
        photo.put("url", url);
        photo.put("category", category);
        photo.put("description",
                StringUtils.hasText(description) ? description : categoryLabel(category));
        return photo;
    }

    private String categoryLabel(String category) {
        if ("cat".equalsIgnoreCase(category)) {
            return "Cat";
        }
        if ("girl".equalsIgnoreCase(category)) {
            return "Girl";
        }
        if ("us".equalsIgnoreCase(category)) {
            return "Us";
        }
        return "Memory";
    }

    private String failureMessage(Throwable failure) {
        String message = failure.getMessage();
        return StringUtils.hasText(message) ? message : failure.getClass().getSimpleName();
    }

    private String trimToEmpty(String value) {
        return value == null ? "" : value.trim();
    }

    private String sanitizeForLog(String value) {
        if (value == null) {
            return "";
        }
        String sanitized = value.replaceAll("[\\p{Cntrl}]", "?");
        return sanitized.length() > MAX_LOG_VALUE_LENGTH
                ? sanitized.substring(0, MAX_LOG_VALUE_LENGTH)
                : sanitized;
    }
}
