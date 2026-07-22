package com.example.guitar.user.service;

import com.example.common.util.OssUploadResult;
import com.example.common.util.OssUtil;
import com.example.guitar.auth.model.GuitarUserPrincipal;
import com.example.guitar.storage.service.OssCleanupService;
import com.example.guitar.web.GuitarApiException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.InputStream;
import java.util.Locale;

@Service
public class GuitarUserServiceImpl implements GuitarUserService {

    private static final Logger LOGGER = LoggerFactory.getLogger(GuitarUserServiceImpl.class);
    private static final int MAX_NICKNAME_LENGTH = 30;
    private static final long MAX_AVATAR_SIZE = 5L * 1024L * 1024L;
    private static final String AVATAR_CLEANUP_TYPE = "AVATAR";

    private final GuitarUserProfilePersistenceService persistenceService;
    private final ObjectProvider<OssUtil> ossUtilProvider;
    private final OssCleanupService ossCleanupService;

    public GuitarUserServiceImpl(GuitarUserProfilePersistenceService persistenceService,
                                 ObjectProvider<OssUtil> ossUtilProvider,
                                 OssCleanupService ossCleanupService) {
        this.persistenceService = persistenceService;
        this.ossUtilProvider = ossUtilProvider;
        this.ossCleanupService = ossCleanupService;
    }

    @Override
    public GuitarUserPrincipal updateNickname(Long userId, String nickname) {
        String normalizedNickname = normalizeNickname(nickname);
        validateNickname(normalizedNickname);
        return GuitarUserPrincipal.from(persistenceService.updateNickname(userId, normalizedNickname).getUser());
    }

    @Override
    public GuitarUserPrincipal updateAvatar(Long userId, MultipartFile avatar) {
        String extension = validateAvatar(avatar);
        OssUtil ossUtil = ossUtilProvider.getIfAvailable();
        if (ossUtil == null) {
            throw new GuitarApiException(HttpStatus.SERVICE_UNAVAILABLE,
                    "OSS_UNAVAILABLE", "头像存储服务暂不可用");
        }

        OssUploadResult uploadResult = uploadAvatar(ossUtil, avatar, extension, userId);
        String objectKey = uploadResult == null ? null : uploadResult.getObjectKey();
        if (objectKey == null || objectKey.trim().isEmpty()) {
            throw new GuitarApiException(HttpStatus.SERVICE_UNAVAILABLE,
                    "OSS_UNAVAILABLE", "头像存储服务暂不可用");
        }

        GuitarUserProfilePersistenceService.ProfileUpdate update;
        try {
            update = persistenceService.replaceAvatar(userId, objectKey.trim());
        } catch (RuntimeException exception) {
            compensateNewAvatar(objectKey);
            throw exception;
        }
        cleanupPreviousAvatar(update.getPreviousAvatarObjectKey());
        return GuitarUserPrincipal.from(update.getUser());
    }

    private String normalizeNickname(String nickname) {
        return nickname == null ? "" : nickname.trim();
    }

    private void validateNickname(String nickname) {
        if (nickname.isEmpty() || nickname.length() > MAX_NICKNAME_LENGTH) {
            throw new GuitarApiException(HttpStatus.BAD_REQUEST,
                    "VALIDATION_ERROR", "昵称长度必须为 1-30 个字符");
        }
    }

    private String validateAvatar(MultipartFile avatar) {
        if (avatar == null || avatar.isEmpty()) {
            throw invalidAvatar();
        }
        if (avatar.getSize() > MAX_AVATAR_SIZE) {
            throw new GuitarApiException(HttpStatus.PAYLOAD_TOO_LARGE,
                    "UPLOAD_LIMIT_EXCEEDED", "头像文件超过 5MB 限制");
        }
        String extension = extensionOf(sanitizeOriginalFilename(avatar.getOriginalFilename()));
        if (!("jpg".equals(extension) || "jpeg".equals(extension)
                || "png".equals(extension) || "webp".equals(extension))) {
            throw invalidAvatar();
        }
        if (!hasExpectedMagic(avatar, extension)) {
            throw invalidAvatar();
        }
        return extension;
    }

    private boolean hasExpectedMagic(MultipartFile avatar, String extension) {
        byte[] header = new byte[12];
        try (InputStream inputStream = avatar.getInputStream()) {
            int offset = 0;
            while (offset < header.length) {
                int count = inputStream.read(header, offset, header.length - offset);
                if (count < 0) {
                    break;
                }
                offset += count;
            }
            if ("jpg".equals(extension) || "jpeg".equals(extension)) {
                return offset >= 3 && (header[0] & 0xFF) == 0xFF
                        && (header[1] & 0xFF) == 0xD8 && (header[2] & 0xFF) == 0xFF;
            }
            if ("png".equals(extension)) {
                byte[] png = new byte[]{(byte) 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A};
                if (offset < png.length) {
                    return false;
                }
                for (int index = 0; index < png.length; index++) {
                    if (header[index] != png[index]) {
                        return false;
                    }
                }
                return true;
            }
            return offset >= 12 && header[0] == 'R' && header[1] == 'I'
                    && header[2] == 'F' && header[3] == 'F'
                    && header[8] == 'W' && header[9] == 'E'
                    && header[10] == 'B' && header[11] == 'P';
        } catch (IOException exception) {
            return false;
        }
    }

    private String sanitizeOriginalFilename(String originalFilename) {
        if (originalFilename == null) {
            return "";
        }
        String normalized = originalFilename.replace('\\', '/');
        int slash = normalized.lastIndexOf('/');
        String basename = slash >= 0 ? normalized.substring(slash + 1) : normalized;
        return basename.replaceAll("[\\p{Cntrl}]", "").trim();
    }

    private String extensionOf(String filename) {
        int dot = filename.lastIndexOf('.');
        return dot < 0 || dot == filename.length() - 1
                ? "" : filename.substring(dot + 1).toLowerCase(Locale.ROOT);
    }

    private String avatarDirectory(Long userId) {
        return "love530/guitar/avatars/" + userId;
    }

    private OssUploadResult uploadAvatar(OssUtil ossUtil, MultipartFile avatar, String extension, Long userId) {
        try (InputStream inputStream = avatar.getInputStream()) {
            return ossUtil.upload(inputStream, avatar.getSize(), "avatar." + extension,
                    mimeTypeFor(extension), avatarDirectory(userId));
        } catch (IOException | RuntimeException exception) {
            throw new GuitarApiException(HttpStatus.SERVICE_UNAVAILABLE,
                    "OSS_UNAVAILABLE", "头像存储服务暂不可用");
        }
    }

    private void compensateNewAvatar(String objectKey) {
        try {
            ossCleanupService.deleteOrEnqueue(objectKey, AVATAR_CLEANUP_TYPE);
        } catch (RuntimeException cleanupException) {
            LOGGER.warn("Failed to compensate uploaded avatar");
        }
    }

    private void cleanupPreviousAvatar(String previousAvatarObjectKey) {
        if (previousAvatarObjectKey == null || previousAvatarObjectKey.trim().isEmpty()) {
            return;
        }
        try {
            ossCleanupService.deleteOrEnqueue(previousAvatarObjectKey, AVATAR_CLEANUP_TYPE);
        } catch (RuntimeException cleanupException) {
            LOGGER.warn("Failed to schedule previous avatar cleanup");
        }
    }

    private String mimeTypeFor(String extension) {
        if ("png".equals(extension)) {
            return "image/png";
        }
        if ("webp".equals(extension)) {
            return "image/webp";
        }
        return "image/jpeg";
    }

    private GuitarApiException invalidAvatar() {
        return new GuitarApiException(HttpStatus.BAD_REQUEST,
                "AVATAR_FILE_INVALID", "头像文件格式不正确");
    }
}
