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

import java.io.IOException;
import java.io.InputStream;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

@Service
public class GuitarSheetServiceImpl implements GuitarSheetService {

    private static final ZoneId SHANGHAI_ZONE = ZoneId.of("Asia/Shanghai");

    private final GuitarSheetDao sheetDao;
    private final GuitarSheetFileDao fileDao;
    private final SheetFileUrlService fileUrlService;
    private final SheetFileValidator sheetFileValidator;
    private final ObjectProvider<OssUtil> ossUtilProvider;
    private final OssCleanupService ossCleanupService;
    private final SheetUploadPersistenceService persistenceService;

    @Autowired
    public GuitarSheetServiceImpl(GuitarSheetDao sheetDao, GuitarSheetFileDao fileDao,
                                  SheetFileUrlService fileUrlService, SheetFileValidator sheetFileValidator,
                                  ObjectProvider<OssUtil> ossUtilProvider, OssCleanupService ossCleanupService,
                                  SheetUploadPersistenceService persistenceService) {
        this.sheetDao = sheetDao;
        this.fileDao = fileDao;
        this.fileUrlService = fileUrlService;
        this.sheetFileValidator = sheetFileValidator;
        this.ossUtilProvider = ossUtilProvider;
        this.ossCleanupService = ossCleanupService;
        this.persistenceService = persistenceService;
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
        try {
            uploadFiles(ossUtil, sheet.getStorageUuid(), request.getFileMode(), validatedFiles, storedFiles);
            persistenceService.persist(sheet, storedFiles);
        } catch (GuitarApiException exception) {
            compensateUploadedObjects(storedFiles);
            throw exception;
        } catch (RuntimeException exception) {
            compensateUploadedObjects(storedFiles);
            throw exception;
        }
        return toUploadResponse(sheet, uploaderNickname, storedFiles);
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
            OssUploadResult uploadResult = upload(ossUtil, validated, directory, serverFilename(fileMode, validated));
            String objectKey = uploadResult == null ? null : uploadResult.getObjectKey();
            if (objectKey == null || objectKey.trim().isEmpty()) {
                throw ossUnavailable();
            }
            GuitarSheetFile file = new GuitarSheetFile();
            file.setObjectKey(objectKey.trim());
            file.setOriginalFilename(validated.getOriginalFilename());
            file.setMimeType(validated.getMimeType());
            file.setFileExtension(validated.getFileExtension());
            file.setFileSize(validated.getFileSize());
            file.setSortOrder(validated.getSortOrder());
            storedFiles.add(file);
        }
    }

    private OssUploadResult upload(OssUtil ossUtil, SheetFileValidator.ValidatedSheetFile validated,
                                   String directory, String serverFilename) {
        try (InputStream input = validated.getMultipartFile().getInputStream()) {
            return ossUtil.upload(input, validated.getFileSize(), serverFilename, validated.getMimeType(), directory);
        } catch (IOException | RuntimeException exception) {
            throw ossUnavailable();
        }
    }

    private String serverFilename(FileMode fileMode, SheetFileValidator.ValidatedSheetFile validated) {
        if (fileMode == FileMode.PDF) {
            return "sheet.pdf";
        }
        return String.format("image-%02d.%s", validated.getSortOrder(), validated.getFileExtension());
    }

    private void compensateUploadedObjects(List<GuitarSheetFile> uploadedFiles) {
        for (GuitarSheetFile file : uploadedFiles) {
            try {
                ossCleanupService.deleteOrEnqueue(file.getObjectKey(), "SHEET_UPLOAD");
            } catch (RuntimeException ignored) {
                // Keep the original upload or persistence failure as the API result.
            }
        }
    }

    private SheetDetailResponse toUploadResponse(GuitarSheet sheet, String uploaderNickname,
                                                  List<GuitarSheetFile> files) {
        sheet.setUploaderNickname(uploaderNickname);
        SheetDetailResponse response = new SheetDetailResponse();
        copySummary(sheet, response);
        response.setDescription(sheet.getDescription());
        List<SheetDetailResponse.FileResponse> fileResponses = new ArrayList<SheetDetailResponse.FileResponse>();
        for (GuitarSheetFile file : files) {
            fileResponses.add(toFileResponse(file));
        }
        response.setFiles(fileResponses);
        return response;
    }

    private GuitarApiException ossUnavailable() {
        return new GuitarApiException(HttpStatus.SERVICE_UNAVAILABLE,
                "OSS_UNAVAILABLE", "曲谱存储服务暂不可用");
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
