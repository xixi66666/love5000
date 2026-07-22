package com.example.guitar.sheet.service;

import com.example.guitar.sheet.dao.GuitarSheetDao;
import com.example.guitar.sheet.dao.GuitarSheetFileDao;
import com.example.guitar.sheet.dto.SheetSearchRequest;
import com.example.guitar.sheet.model.GuitarSheet;
import com.example.guitar.sheet.model.GuitarSheetFile;
import com.example.guitar.sheet.vo.SheetDetailResponse;
import com.example.guitar.sheet.vo.SheetSummaryResponse;
import com.example.guitar.web.GuitarApiException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.LocalDate;
import java.util.Collections;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class GuitarSheetServiceImplTest {

    private GuitarSheetDao sheetDao;
    private GuitarSheetFileDao fileDao;
    private SheetFileUrlService fileUrlService;
    private GuitarSheetServiceImpl service;

    @BeforeEach
    void setUp() {
        sheetDao = mock(GuitarSheetDao.class);
        fileDao = mock(GuitarSheetFileDao.class);
        fileUrlService = mock(SheetFileUrlService.class);
        service = new GuitarSheetServiceImpl(sheetDao, fileDao, fileUrlService);
    }

    @Test
    void searchEscapesLikeWildcardsAndUsesBoundedPagination() {
        SheetSearchRequest request = new SheetSearchRequest();
        request.setKeyword("a%_b");
        request.setSheetType("tab");
        request.setDifficulty("beginner");
        request.setKeySignature("C");
        request.setCapoPosition(3);
        request.setTuning("Drop D");
        request.setSort("MOST_VIEWED");
        request.setPage(2);
        request.setSize(20);
        when(sheetDao.countPublicSheets(any(SheetSearchRequest.class))).thenReturn(1L);
        when(sheetDao.findPublicSheets(any(SheetSearchRequest.class))).thenReturn(Collections.singletonList(sheet(9L)));

        GuitarSheetService.SheetSearchResult result = service.searchPublicSheets(request);

        assertThat(result.getTotal()).isEqualTo(1L);
        assertThat(result.getRecords()).extracting(SheetSummaryResponse::getId).containsExactly(9L);
        assertThat(request.getKeywordLike()).isEqualTo("%a\\%\\_b%");
        assertThat(request.getOffset()).isEqualTo(20);
        assertThat(request.getSort()).isEqualTo("MOST_VIEWED");
        assertThat(request.getSheetType()).isEqualTo("TAB");
        assertThat(request.getDifficulty()).isEqualTo("BEGINNER");
        assertThat(request.getKeySignature()).isEqualTo("C");
        assertThat(request.getCapoPosition()).isEqualTo(3);
        assertThat(request.getTuning()).isEqualTo("Drop D");
        verify(sheetDao).countPublicSheets(request);
        verify(sheetDao).findPublicSheets(request);
    }

    @Test
    void searchRejectsUnknownSortAndOutOfRangePaginationBeforeDaoAccess() {
        SheetSearchRequest injection = new SheetSearchRequest();
        injection.setSort("id desc; drop table guitar_sheet");
        assertApiError(() -> service.searchPublicSheets(injection), "VALIDATION_ERROR");

        SheetSearchRequest tooLarge = new SheetSearchRequest();
        tooLarge.setSize(51);
        assertApiError(() -> service.searchPublicSheets(tooLarge), "VALIDATION_ERROR");
        verifyNoInteractions(sheetDao, fileDao);
    }

    @Test
    void detailReturnsAnonymousPublicRecordFilesAndCountsViewForShanghaiDay() {
        GuitarSheet publicSheet = sheet(9L);
        GuitarSheetFile file = new GuitarSheetFile();
        file.setId(3L);
        file.setObjectKey("guitar/sheets/9/intro tab.pdf");
        file.setOriginalFilename("intro-tab.pdf");
        file.setMimeType("application/pdf");
        file.setFileExtension("pdf");
        file.setFileSize(101L);
        file.setSortOrder(1);
        when(sheetDao.findPublishedById(9L)).thenReturn(publicSheet);
        when(fileDao.findBySheetId(9L)).thenReturn(Collections.singletonList(file));
        when(fileUrlService.getFileUrl(file.getObjectKey())).thenReturn("https://cdn.example/sheet.pdf");
        when(sheetDao.incrementViewCount(9L)).thenReturn(1);
        when(sheetDao.incrementDailyViewCount(any(LocalDate.class))).thenReturn(1);

        SheetDetailResponse detail = service.getPublicSheetDetail(9L);

        assertThat(detail.getId()).isEqualTo(9L);
        assertThat(detail.getViewCount()).isEqualTo(13L);
        assertThat(detail.getFiles()).hasSize(1);
        assertThat(detail.getFiles().get(0).getUrl()).isEqualTo("https://cdn.example/sheet.pdf");
        verify(sheetDao).incrementViewCount(9L);
        verify(sheetDao).incrementDailyViewCount(eq(LocalDate.now(java.time.ZoneId.of("Asia/Shanghai"))));
    }

    @Test
    void detailDoesNotIncrementMissingOrOfflineSheet() {
        when(sheetDao.findPublishedById(10L)).thenReturn(null);

        assertApiError(() -> service.getPublicSheetDetail(10L), "SHEET_NOT_FOUND");
    }

    @Test
    void detailFailsWhenViewIncrementDoesNotAffectExactlyOnePublishedSheet() {
        when(sheetDao.findPublishedById(9L)).thenReturn(sheet(9L));
        when(fileDao.findBySheetId(9L)).thenReturn(Collections.<GuitarSheetFile>emptyList());
        when(sheetDao.incrementViewCount(9L)).thenReturn(0);

        assertApiError(() -> service.getPublicSheetDetail(9L), "SHEET_VIEW_INCREMENT_FAILED");
    }

    private GuitarSheet sheet(Long id) {
        GuitarSheet sheet = new GuitarSheet();
        sheet.setId(id);
        sheet.setSongName("Song");
        sheet.setSinger("Singer");
        sheet.setArranger("Arranger");
        sheet.setSheetType("TAB");
        sheet.setDifficulty("BEGINNER");
        sheet.setKeySignature("C");
        sheet.setCapoPosition(0);
        sheet.setTuning("Standard");
        sheet.setUploaderNickname("Uploader");
        sheet.setViewCount(12L);
        sheet.setFavoriteCount(5L);
        sheet.setDescription("Description");
        sheet.setCreateTime(java.time.LocalDateTime.of(2026, 7, 22, 10, 0));
        sheet.setUpdateTime(java.time.LocalDateTime.of(2026, 7, 22, 10, 0));
        return sheet;
    }

    private void assertApiError(ThrowingCallable callable, String code) {
        assertThatThrownBy(callable::call).isInstanceOfSatisfying(GuitarApiException.class,
                exception -> assertThat(exception.getCode()).isEqualTo(code));
    }

    @FunctionalInterface
    private interface ThrowingCallable {
        void call();
    }
}
