package com.example.guitar.sheet.service;

import com.example.common.util.OssUploadResult;
import com.example.common.util.OssUtil;
import com.example.guitar.sheet.dao.GuitarSheetDao;
import com.example.guitar.sheet.dao.GuitarSheetFileDao;
import com.example.guitar.sheet.dto.SheetSaveRequest;
import com.example.guitar.sheet.model.FileMode;
import com.example.guitar.sheet.model.GuitarSheet;
import com.example.guitar.sheet.model.GuitarSheetFile;
import com.example.guitar.storage.service.OssCleanupService;
import com.example.guitar.storage.model.OssCleanupTask;
import com.example.guitar.web.GuitarApiException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.HashMap;
import java.util.UUID;

/** Coordinates ownership checks, remote storage, and transactional mutation persistence. */
@Service
public class GuitarSheetMutationService {
    private static final Logger LOGGER = LoggerFactory.getLogger(GuitarSheetMutationService.class);
    private final GuitarSheetDao sheetDao;
    private final GuitarSheetFileDao fileDao;
    private final SheetFileValidator validator;
    private final SheetFileUrlService urlService;
    private final ObjectProvider<OssUtil> ossProvider;
    private final OssCleanupService cleanupService;
    private final SheetMutationPersistenceService persistenceService;

    public GuitarSheetMutationService(GuitarSheetDao sheetDao, GuitarSheetFileDao fileDao, SheetFileValidator validator,
                                      SheetFileUrlService urlService, ObjectProvider<OssUtil> ossProvider,
                                      OssCleanupService cleanupService, SheetMutationPersistenceService persistenceService) {
        this.sheetDao = sheetDao; this.fileDao = fileDao; this.validator = validator; this.urlService = urlService;
        this.ossProvider = ossProvider; this.cleanupService = cleanupService; this.persistenceService = persistenceService;
    }

    public MutationFiles update(long ownerId, long sheetId, SheetSaveRequest request) {
        requireOwnerId(ownerId);
        GuitarSheet current = requireOwner(sheetId, ownerId);
        validator.normalizeAndValidateMetadataForUpdate(request);
        List<GuitarSheetFile> files = fileDao.findBySheetId(current.getId());
        Map<String, String> urls = precomputeUrls(files);
        GuitarSheet updated = persistenceService.updateMetadata(current, request);
        return new MutationFiles(updated, files, urls);
    }

    public MutationFiles replaceFiles(long ownerId, long sheetId, FileMode mode,
                                               List<MultipartFile> multipartFiles) {
        requireOwnerId(ownerId);
        GuitarSheet current = requireOwner(sheetId, ownerId);
        String expectedStorageUuid = current.getStorageUuid();
        List<SheetFileValidator.ValidatedSheetFile> validated = validator.validateFiles(mode, multipartFiles);
        OssUtil oss = ossProvider.getIfAvailable();
        if (oss == null) throw ossUnavailable();

        String newStorageUuid = nextStorageUuid(current.getStorageUuid());
        List<GuitarSheetFile> newFiles = new ArrayList<GuitarSheetFile>();
        try {
            upload(oss, newStorageUuid, mode, validated, newFiles);
            Map<String, String> urls = precomputeUrls(newFiles);
            SheetMutationPersistenceService.CleanupOutbox cleanupOutbox = persistenceService.replaceFiles(
                    current, expectedStorageUuid, newStorageUuid, mode, newFiles);
            current.setStorageUuid(newStorageUuid);
            current.setFileMode(mode.name());
            cleanupCommittedTasks(cleanupOutbox);
            return new MutationFiles(current, newFiles, urls);
        } catch (RuntimeException failure) {
            cleanupNewFiles(newFiles, failure);
            throw failure;
        }
    }

    public void delete(long ownerId, long sheetId) {
        requireOwnerId(ownerId);
        GuitarSheet current = requireOwner(sheetId, ownerId);
        cleanupCommittedTasks(persistenceService.softDelete(current));
    }

    private GuitarSheet requireOwner(Long sheetId, Long ownerId) {
        if (sheetId == null || sheetId < 1) throw new GuitarApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", "请求参数不正确");
        GuitarSheet current = sheetDao.findActiveByIdForOwner(sheetId, ownerId);
        if (current != null) return current;
        if (sheetDao.existsActiveById(sheetId) > 0) {
            throw new GuitarApiException(HttpStatus.FORBIDDEN, "FORBIDDEN", "只能修改自己的曲谱");
        }
        throw new GuitarApiException(HttpStatus.NOT_FOUND, "SHEET_NOT_FOUND", "曲谱不存在或已删除");
    }

    private void requireOwnerId(Long ownerId) {
        if (ownerId == null || ownerId < 1) throw new GuitarApiException(HttpStatus.UNAUTHORIZED, "AUTH_REQUIRED", "请先登录");
    }

    private void upload(OssUtil oss, String storageUuid, FileMode mode,
                        List<SheetFileValidator.ValidatedSheetFile> validated, List<GuitarSheetFile> target) {
        String directory = "love530/guitar/sheets/" + storageUuid + (mode == FileMode.PDF ? "/pdf" : "/images");
        for (SheetFileValidator.ValidatedSheetFile source : validated) {
            GuitarSheetFile file = new GuitarSheetFile();
            file.setObjectKey(directory + "/" + filename(mode, source)); file.setOriginalFilename(source.getOriginalFilename());
            file.setMimeType(source.getMimeType()); file.setFileExtension(source.getFileExtension());
            file.setFileSize(source.getFileSize()); file.setSortOrder(source.getSortOrder()); target.add(file);
            try (InputStream input = source.getMultipartFile().getInputStream()) {
                OssUploadResult result = oss.uploadWithObjectKey(input, source.getFileSize(), file.getObjectKey(),
                        source.getOriginalFilename(), source.getMimeType());
                if (result == null || !file.getObjectKey().equals(result.getObjectKey())) throw ossUnavailable();
            } catch (IOException | RuntimeException failure) { throw ossUnavailable(failure); }
        }
    }

    private Map<String, String> precomputeUrls(List<GuitarSheetFile> files) {
        Map<String, String> urls = new HashMap<String, String>();
        for (GuitarSheetFile file : files) {
            String url = urlService.getFileUrl(file.getObjectKey());
            if (url == null || url.trim().isEmpty()) throw ossUnavailable();
            urls.put(file.getObjectKey(), url);
        }
        return urls;
    }

    private String filename(FileMode mode, SheetFileValidator.ValidatedSheetFile file) {
        return mode == FileMode.PDF ? "sheet.pdf" : String.format("image-%02d.%s", file.getSortOrder(), file.getFileExtension());
    }

    private String nextStorageUuid(String previous) {
        String candidate;
        do {
            candidate = UUID.randomUUID().toString();
        } while (candidate.equals(previous));
        return candidate;
    }

    private void cleanupNewFiles(List<GuitarSheetFile> files, Throwable failure) { cleanup(files, "SHEET_REPLACE_NEW", failure); }
    private void cleanup(List<GuitarSheetFile> files, String type, Throwable original) {
        for (GuitarSheetFile file : files) {
            try { cleanupService.deleteOrEnqueue(file.getObjectKey(), type); }
            catch (RuntimeException cleanupFailure) {
                if (original != null) original.addSuppressed(cleanupFailure);
                else LOGGER.warn("Post-commit sheet object cleanup could not be queued, objectKey={}", file.getObjectKey());
            }
        }
    }

    private void cleanupCommittedTasks(SheetMutationPersistenceService.CleanupOutbox outbox) {
        if (outbox == null) return;
        for (OssCleanupTask task : outbox.getTasks()) {
            try {
                cleanupService.deleteEnqueued(task);
            } catch (RuntimeException failure) {
                LOGGER.warn("Immediate cleanup deferred to durable task, taskId={}, objectKey={}",
                        task.getId(), task.getObjectKey(), failure);
            }
        }
    }

    private GuitarApiException ossUnavailable() { return ossUnavailable(null); }

    private GuitarApiException ossUnavailable(Throwable cause) {
        GuitarApiException exception = new GuitarApiException(HttpStatus.SERVICE_UNAVAILABLE,
                "OSS_UNAVAILABLE", "曲谱存储服务暂不可用");
        if (cause != null) exception.initCause(cause);
        return exception;
    }

    public static final class MutationFiles {
        private final GuitarSheet sheet;
        private final List<GuitarSheetFile> files;
        private final Map<String, String> urls;
        MutationFiles(GuitarSheet sheet, List<GuitarSheetFile> files, Map<String, String> urls) {
            this.sheet = sheet; this.files = files; this.urls = urls;
        }
        public GuitarSheet getSheet() { return sheet; }
        public List<GuitarSheetFile> getFiles() { return files; }
        public Map<String, String> getUrls() { return urls; }
    }
}
