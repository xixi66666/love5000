package com.example.guitar.sheet.service;

import com.example.guitar.sheet.dao.GuitarSheetDao;
import com.example.guitar.sheet.dao.GuitarSheetFileDao;
import com.example.guitar.sheet.dto.SheetSearchRequest;
import com.example.guitar.sheet.model.GuitarSheet;
import com.example.guitar.sheet.model.GuitarSheetFile;
import com.example.guitar.sheet.vo.SheetDetailResponse;
import com.example.guitar.sheet.vo.SheetSummaryResponse;
import com.example.guitar.web.GuitarApiException;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.List;

@Service
public class GuitarSheetServiceImpl implements GuitarSheetService {

    private static final ZoneId SHANGHAI_ZONE = ZoneId.of("Asia/Shanghai");

    private final GuitarSheetDao sheetDao;
    private final GuitarSheetFileDao fileDao;
    private final SheetFileUrlService fileUrlService;

    public GuitarSheetServiceImpl(GuitarSheetDao sheetDao, GuitarSheetFileDao fileDao,
                                  SheetFileUrlService fileUrlService) {
        this.sheetDao = sheetDao;
        this.fileDao = fileDao;
        this.fileUrlService = fileUrlService;
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
