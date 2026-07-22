package com.example.guitar.sheet.service;

import com.example.common.util.OssUploadResult;
import com.example.common.util.OssUtil;
import com.example.guitar.sheet.dao.GuitarSheetDao;
import com.example.guitar.sheet.dao.GuitarSheetFileDao;
import com.example.guitar.sheet.dto.SheetSearchRequest;
import com.example.guitar.sheet.dto.SheetSaveRequest;
import com.example.guitar.sheet.model.FileMode;
import com.example.guitar.sheet.model.GuitarSheet;
import com.example.guitar.sheet.model.GuitarSheetFile;
import com.example.guitar.storage.service.OssCleanupService;
import com.example.guitar.sheet.vo.SheetDetailResponse;
import com.example.guitar.sheet.vo.SheetSummaryResponse;
import com.example.guitar.web.GuitarApiException;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.io.InputStream;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
public class GuitarSheetServiceImpl implements GuitarSheetService {

    private static final ZoneId SHANGHAI_ZONE = ZoneId.of("Asia/Shanghai");
    private static final Logger LOGGER = LoggerFactory.getLogger(GuitarSheetServiceImpl.class);

    private final GuitarSheetDao sheetDao;
    private final GuitarSheetFileDao fileDao;
    private final SheetFileUrlService fileUrlService;
    private final SheetFileValidator sheetFileValidator;
    private final ObjectProvider<OssUtil> ossUtilProvider;
    private final OssCleanupService ossCleanupService;
    private final SheetUploadPersistenceService persistenceService;
    private final GuitarSheetMutationService mutationService;

    public GuitarSheetServiceImpl(GuitarSheetDao sheetDao, GuitarSheetFileDao fileDao,
                                  SheetFileUrlService fileUrlService, SheetFileValidator sheetFileValidator,
                                  ObjectProvider<OssUtil> ossUtilProvider, OssCleanupService ossCleanupService,
                                  SheetUploadPersistenceService persistenceService) {
        this(sheetDao, fileDao, fileUrlService, sheetFileValidator, ossUtilProvider, ossCleanupService,
                persistenceService, null);
    }

    @Autowired
    public GuitarSheetServiceImpl(GuitarSheetDao sheetDao, GuitarSheetFileDao fileDao,
                                  SheetFileUrlService fileUrlService, SheetFileValidator sheetFileValidator,
                                  ObjectProvider<OssUtil> ossUtilProvider, OssCleanupService ossCleanupService,
                                  SheetUploadPersistenceService persistenceService,
                                  GuitarSheetMutationService mutationService) {
        this.sheetDao = sheetDao;
        this.fileDao = fileDao;
        this.fileUrlService = fileUrlService;
        this.sheetFileValidator = sheetFileValidator;
        this.ossUtilProvider = ossUtilProvider;
        this.ossCleanupService = ossCleanupService;
        this.persistenceService = persistenceService;
        this.mutationService = mutationService;
    }

    @Override
    public SheetSearchResult searchPublicSheets(SheetSearchRequest request) {
        SheetSearchRequest effectiveRequest = request == null ? new SheetSearchRequest() : request;
        effectiveRequest.normalizeAndValidate();
        long total = sheetDao.countPublicSheets(effectiveRequest);
        List<GuitarSheet> sheets = sheetDao.findPublicSheets(effectiveRequest);
        List<SheetSummaryResponse> records = new ArrayList<SheetSummaryResponse>();
        for (GuitarSheet sheet : sheets) {
            records.add(toSummary(sheet));
        }
        return new SheetSearchResult(records, total, effectiveRequest.getPage(), effectiveRequest.getSize());
    }

    @Override
    @Transactional
    public SheetDetailResponse getPublicSheetDetail(Long id) {
        if (id == null || id < 1) {
            throw new GuitarApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", "请求参数不正确");
        }
        GuitarSheet sheet = sheetDao.findPublishedById(id);
        if (sheet == null) {
            throw new GuitarApiException(HttpStatus.NOT_FOUND, "SHEET_NOT_FOUND", "曲谱不存在或不可访问");
        }
        List<SheetDetailResponse.FileResponse> files = new ArrayList<SheetDetailResponse.FileResponse>();
        for (GuitarSheetFile file : fileDao.findBySheetId(id)) {
            files.add(toFileResponse(file));
        }
        if (sheetDao.incrementViewCount(id) != 1) {
            throw new GuitarApiException(HttpStatus.INTERNAL_SERVER_ERROR, "SHEET_VIEW_INCREMENT_FAILED", "曲谱访问记录失败");
        }
        sheetDao.incrementDailyViewCount(LocalDate.now(SHANGHAI_ZONE));

        SheetDetailResponse response = new SheetDetailResponse();
        copySummary(sheet, response);
        response.setViewCount((sheet.getViewCount() == null ? 0L : sheet.getViewCount()) + 1L);
        response.setDescription(sheet.getDescription());
        response.setFiles(files);
        return response;
    }

    @Override
    public SheetDetailResponse createSheet(Long uploaderId, String uploaderNickname,
                                           SheetSaveRequest request, List<MultipartFile> files) {
        if (uploaderId == null || uploaderId < 1) {
            throw new GuitarApiException(HttpStatus.UNAUTHORIZED, "AUTH_REQUIRED", "请先登录");
        }
        sheetFileValidator.normalizeAndValidateMetadata(request);
        List<SheetFileValidator.ValidatedSheetFile> validatedFiles =
                sheetFileValidator.validateFiles(request.getFileMode(), files);
        OssUtil ossUtil = ossUtilProvider.getIfAvailable();
        if (ossUtil == null) {
            throw ossUnavailable();
        }

        GuitarSheet sheet = toSheet(uploaderId, request);
        List<GuitarSheetFile> storedFiles = new ArrayList<GuitarSheetFile>();
        Map<String, String> fileUrls;
        try {
            uploadFiles(ossUtil, sheet.getStorageUuid(), request.getFileMode(), validatedFiles, storedFiles);
            fileUrls = precomputeFileUrls(storedFiles);
            persistenceService.persist(sheet, storedFiles);
        } catch (RuntimeException exception) {
            compensateUploadedObjects(storedFiles, exception);
            throw exception;
        }
        return toUploadResponse(sheet, uploaderNickname, storedFiles, fileUrls);
    }

    @Override
    public SheetDetailResponse update(long userId, long sheetId, SheetSaveRequest request) {
        GuitarSheetMutationService.MutationFiles result = mutations().update(userId, sheetId, request);
        GuitarSheet sheet = result.getSheet();
        SheetDetailResponse response = new SheetDetailResponse();
        copySummary(sheet, response); response.setDescription(sheet.getDescription());
        List<SheetDetailResponse.FileResponse> responses = new ArrayList<SheetDetailResponse.FileResponse>();
        for (GuitarSheetFile file : result.getFiles()) {
            responses.add(toFileResponse(file, result.getUrls().get(file.getObjectKey())));
        }
        response.setFiles(responses);
        return response;
    }

    @Override
    public SheetDetailResponse replaceFiles(long userId, long sheetId, FileMode mode, List<MultipartFile> files) {
        GuitarSheetMutationService.MutationFiles result = mutations().replaceFiles(userId, sheetId, mode, files);
        SheetDetailResponse response = new SheetDetailResponse();
        copySummary(result.getSheet(), response); response.setDescription(result.getSheet().getDescription());
        List<SheetDetailResponse.FileResponse> responses = new ArrayList<SheetDetailResponse.FileResponse>();
        for (GuitarSheetFile file : result.getFiles()) responses.add(toFileResponse(file, result.getUrls().get(file.getObjectKey())));
        response.setFiles(responses);
        return response;
    }

    @Override
    public void delete(long userId, long sheetId) { mutations().delete(userId, sheetId); }

    private GuitarSheetMutationService mutations() {
        if (mutationService == null) throw new IllegalStateException("Sheet mutation service is unavailable");
        return mutationService;
    }

    private GuitarSheet toSheet(Long uploaderId, SheetSaveRequest request) {
        GuitarSheet sheet = new GuitarSheet();
        sheet.setUploaderId(uploaderId);
        sheet.setSongName(request.getSongName());
        sheet.setSinger(request.getSinger());
        sheet.setArranger(request.getArranger());
        sheet.setDescription(request.getDescription());
        sheet.setKeywords(request.getKeywords());
        sheet.setSheetType(request.getSheetType().name());
        sheet.setDifficulty(request.getDifficulty().name());
        sheet.setKeySignature(request.getKeySignature());
        sheet.setCapoPosition(request.getCapoPosition());
        sheet.setTuning(request.getTuning());
        sheet.setFileMode(request.getFileMode().name());
        sheet.setStorageUuid(UUID.randomUUID().toString());
        sheet.setStatus("PUBLISHED");
        sheet.setViewCount(0L);
        sheet.setFavoriteCount(0L);
        return sheet;
    }

    private void uploadFiles(OssUtil ossUtil, String storageUuid, FileMode fileMode,
                             List<SheetFileValidator.ValidatedSheetFile> validatedFiles,
                             List<GuitarSheetFile> storedFiles) {
        String directory = "love530/guitar/sheets/" + storageUuid
                + (fileMode == FileMode.PDF ? "/pdf" : "/images");
        for (SheetFileValidator.ValidatedSheetFile validated : validatedFiles) {
            GuitarSheetFile file = new GuitarSheetFile();
            file.setObjectKey(directory + "/" + serverFilename(fileMode, validated));
            file.setOriginalFilename(validated.getOriginalFilename());
            file.setMimeType(validated.getMimeType());
            file.setFileExtension(validated.getFileExtension());
            file.setFileSize(validated.getFileSize());
            file.setSortOrder(validated.getSortOrder());
            // 在远程调用前登记预声明键，即使 OSS 已接受对象后本地抛错也能补偿。
            storedFiles.add(file);
            OssUploadResult uploadResult = upload(ossUtil, validated, file.getObjectKey());
            String objectKey = uploadResult == null ? null : uploadResult.getObjectKey();
            if (objectKey == null || !file.getObjectKey().equals(objectKey.trim())) {
                throw ossUnavailable();
            }
        }
    }

    private OssUploadResult upload(OssUtil ossUtil, SheetFileValidator.ValidatedSheetFile validated,
                                   String objectKey) {
        try (InputStream input = validated.getMultipartFile().getInputStream()) {
            return ossUtil.uploadWithObjectKey(input, validated.getFileSize(), objectKey,
                    validated.getOriginalFilename(), validated.getMimeType());
        } catch (IOException | RuntimeException exception) {
            throw ossUnavailable(exception);
        }
    }

    private String serverFilename(FileMode fileMode, SheetFileValidator.ValidatedSheetFile validated) {
        if (fileMode == FileMode.PDF) {
            return "sheet.pdf";
        }
        return String.format("image-%02d.%s", validated.getSortOrder(), validated.getFileExtension());
    }

    private Map<String, String> precomputeFileUrls(List<GuitarSheetFile> files) {
        Map<String, String> fileUrls = new HashMap<String, String>();
        for (GuitarSheetFile file : files) {
            String url = fileUrlService.getFileUrl(file.getObjectKey());
            if (url == null || url.trim().isEmpty()) {
                throw ossUnavailable();
            }
            fileUrls.put(file.getObjectKey(), url);
        }
        return fileUrls;
    }

    private void compensateUploadedObjects(List<GuitarSheetFile> uploadedFiles, Throwable originalFailure) {
        for (GuitarSheetFile file : uploadedFiles) {
            try {
                ossCleanupService.deleteOrEnqueue(file.getObjectKey(), "SHEET_UPLOAD");
            } catch (RuntimeException cleanupFailure) {
                originalFailure.addSuppressed(cleanupFailure);
                LOGGER.warn("Failed to compensate sheet object, objectKey={}",
                        sanitizeForLog(file.getObjectKey()), cleanupFailure);
            }
        }
    }

    private SheetDetailResponse toUploadResponse(GuitarSheet sheet, String uploaderNickname,
                                                  List<GuitarSheetFile> files, Map<String, String> fileUrls) {
        sheet.setUploaderNickname(uploaderNickname);
        SheetDetailResponse response = new SheetDetailResponse();
        copySummary(sheet, response);
        response.setDescription(sheet.getDescription());
        List<SheetDetailResponse.FileResponse> fileResponses = new ArrayList<SheetDetailResponse.FileResponse>();
        for (GuitarSheetFile file : files) {
            fileResponses.add(toFileResponse(file, fileUrls.get(file.getObjectKey())));
        }
        response.setFiles(fileResponses);
        return response;
    }

    private SheetDetailResponse.FileResponse toFileResponse(GuitarSheetFile source, String url) {
        SheetDetailResponse.FileResponse response = new SheetDetailResponse.FileResponse();
        response.setId(source.getId());
        response.setOriginalFilename(source.getOriginalFilename());
        response.setMimeType(source.getMimeType());
        response.setFileExtension(source.getFileExtension());
        response.setFileSize(source.getFileSize());
        response.setSortOrder(source.getSortOrder());
        response.setCreateTime(source.getCreateTime());
        response.setUrl(url);
        return response;
    }

    private String sanitizeForLog(String value) {
        if (value == null) {
            return "";
        }
        String sanitized = value.replaceAll("[\\p{Cntrl}]", "?");
        return sanitized.length() > 200 ? sanitized.substring(0, 200) : sanitized;
    }

    private GuitarApiException ossUnavailable() {
        return ossUnavailable(null);
    }

    private GuitarApiException ossUnavailable(Throwable cause) {
        GuitarApiException exception = new GuitarApiException(HttpStatus.SERVICE_UNAVAILABLE,
                "OSS_UNAVAILABLE", "曲谱存储服务暂不可用");
        if (cause != null) exception.initCause(cause);
        return exception;
    }

    private SheetSummaryResponse toSummary(GuitarSheet sheet) {
        SheetSummaryResponse response = new SheetSummaryResponse();
        copySummary(sheet, response);
        return response;
    }

    private void copySummary(GuitarSheet source, SheetSummaryResponse target) {
        target.setId(source.getId());
        target.setSongName(source.getSongName());
        target.setSinger(source.getSinger());
        target.setArranger(source.getArranger());
        target.setSheetType(source.getSheetType());
        target.setDifficulty(source.getDifficulty());
        target.setKeySignature(source.getKeySignature());
        target.setCapoPosition(source.getCapoPosition());
        target.setTuning(source.getTuning());
        target.setUploaderNickname(source.getUploaderNickname());
        target.setViewCount(source.getViewCount());
        target.setFavoriteCount(source.getFavoriteCount());
        target.setCreateTime(source.getCreateTime());
        target.setUpdateTime(source.getUpdateTime());
    }

    private SheetDetailResponse.FileResponse toFileResponse(GuitarSheetFile source) {
        SheetDetailResponse.FileResponse response = new SheetDetailResponse.FileResponse();
        response.setId(source.getId());
        response.setOriginalFilename(source.getOriginalFilename());
        response.setMimeType(source.getMimeType());
        response.setFileExtension(source.getFileExtension());
        response.setFileSize(source.getFileSize());
        response.setSortOrder(source.getSortOrder());
        response.setCreateTime(source.getCreateTime());
        response.setUrl(fileUrlService.getFileUrl(source.getObjectKey()));
        return response;
    }
}
