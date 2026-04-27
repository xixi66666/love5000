package com.ycxandwuqian.love.controller;

import com.example.common.util.OssUploadResult;
import com.example.common.util.OssUtil;
import com.ycxandwuqian.love.model.PhotoRecord;
import com.ycxandwuqian.love.repository.PhotoRepository;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.dao.DataAccessException;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
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
import java.util.Optional;
import java.util.Set;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/photos")
public class UploadPhotoController {

    private static final Set<String> ALLOWED_CATEGORIES = new HashSet<String>(Arrays.asList("cat", "girl", "us"));

    private static final DateTimeFormatter TIME_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private final ObjectProvider<OssUtil> ossUtilProvider;

    private final PhotoRepository photoRepository;

    public UploadPhotoController(ObjectProvider<OssUtil> ossUtilProvider, PhotoRepository photoRepository) {
        this.ossUtilProvider = ossUtilProvider;
        this.photoRepository = photoRepository;
    }

    @PostMapping("/upload")
    public Map<String, Object> uploadPhoto(@RequestParam("file") MultipartFile file,
                                           @RequestParam("category") String category,
                                           @RequestParam(value = "description", defaultValue = "") String description) {
        Map<String, Object> response = new HashMap<String, Object>();

        try {
            OssUtil ossUtil = ossUtilProvider.getIfAvailable();
            if (ossUtil == null) {
                response.put("success", false);
                response.put("message", "OSS is not configured");
                return response;
            }

            if (file.isEmpty()) {
                response.put("success", false);
                response.put("message", "Please select a file");
                return response;
            }

            String originalFilename = file.getOriginalFilename();
            if (!isSupportedImage(originalFilename)) {
                response.put("success", false);
                response.put("message", "Only jpg, jpeg, png, gif and webp images are supported");
                return response;
            }

            String normalizedCategory = normalizeCategory(category);
            if (!ALLOWED_CATEGORIES.contains(normalizedCategory)) {
                response.put("success", false);
                response.put("message", "Unsupported photo category");
                return response;
            }

            String sanitizedDescription = StringUtils.hasText(description) ? description.trim() : "";
            OssUploadResult uploadResult = ossUtil.upload(file, "love530/lovestory/photos/" + normalizedCategory);
            Long photoId = photoRepository.save(uploadResult.getObjectKey(), normalizedCategory);

            PhotoRecord photoRecord = new PhotoRecord();
            photoRecord.setId(photoId);
            photoRecord.setPath(uploadResult.getObjectKey());
            photoRecord.setType(normalizedCategory);
            photoRecord.setCreateTime(LocalDateTime.now());

            response.put("success", true);
            response.put("message", "Upload succeeded");
            response.put("url", uploadResult.getUrl());
            response.put("photo", buildPhotoResponse(uploadResult.getUrl(), normalizedCategory, sanitizedDescription, photoRecord));
            return response;
        } catch (IllegalArgumentException | IllegalStateException | DataAccessException e) {
            response.put("success", false);
            response.put("message", "Upload failed: " + e.getMessage());
            return response;
        }
    }

    @GetMapping
    public Map<String, Object> listPhotos() {
        Map<String, Object> response = new HashMap<String, Object>();

        try {
            List<Map<String, Object>> photos = photoRepository.findAll().stream()
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
            response.put("message", "Failed to load photos: " + e.getMessage());
            response.put("photos", Collections.emptyList());
        }

        return response;
    }

    @DeleteMapping("/{id}")
    public Map<String, Object> deletePhoto(@PathVariable("id") Long id) {
        Map<String, Object> response = new HashMap<String, Object>();

        try {
            Optional<PhotoRecord> photoOptional = photoRepository.findById(id);
            if (!photoOptional.isPresent()) {
                response.put("success", false);
                response.put("message", "Photo not found");
                return response;
            }

            PhotoRecord photoRecord = photoOptional.get();
            OssUtil ossUtil = ossUtilProvider.getIfAvailable();
            if (ossUtil != null && StringUtils.hasText(photoRecord.getPath())) {
                ossUtil.delete(photoRecord.getPath());
            }

            boolean deleted = photoRepository.deleteById(id);
            if (!deleted) {
                response.put("success", false);
                response.put("message", "Failed to delete photo record");
                return response;
            }

            response.put("success", true);
            response.put("message", "Photo deleted");
            response.put("id", id);
        } catch (IllegalArgumentException | IllegalStateException | DataAccessException e) {
            response.put("success", false);
            response.put("message", "Delete failed: " + e.getMessage());
        }

        return response;
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

    private Map<String, Object> buildPhotoResponse(String url, String category, String description, PhotoRecord photoRecord) {
        Map<String, Object> photo = new LinkedHashMap<String, Object>();
        if (photoRecord != null) {
            photo.put("id", photoRecord.getId());
            if (photoRecord.getCreateTime() != null) {
                photo.put("createTime", TIME_FORMATTER.format(photoRecord.getCreateTime()));
            }
        }
        photo.put("url", url);
        photo.put("category", category);
        photo.put("description", StringUtils.hasText(description) ? description : categoryLabel(category));
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
}
