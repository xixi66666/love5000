package com.example.guitar.sheet.service;

import com.example.common.util.OssUploadResult;
import com.example.common.util.OssUtil;
import com.example.guitar.sheet.dto.SheetSaveRequest;
import com.example.guitar.sheet.model.FileMode;
import com.example.guitar.sheet.model.GuitarSheet;
import com.example.guitar.sheet.model.SheetDifficulty;
import com.example.guitar.sheet.model.SheetType;
import com.example.guitar.sheet.vo.SheetDetailResponse;
import com.example.guitar.storage.service.OssCleanupService;
import com.example.guitar.web.GuitarApiException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.mock.web.MockMultipartFile;

import java.io.InputStream;
import java.util.Arrays;
import java.util.Collections;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class GuitarSheetUploadServiceTest {

    private GuitarSheetDaoFixture daoFixture;
    private ObjectProvider<OssUtil> ossUtilProvider;
    private OssUtil ossUtil;
    private OssCleanupService cleanupService;
    private SheetFileUrlService urlService;
    private GuitarSheetServiceImpl service;

    @BeforeEach
    void setUp() {
        daoFixture = new GuitarSheetDaoFixture();
        ossUtilProvider = ossProvider();
        ossUtil = mock(OssUtil.class);
        cleanupService = mock(OssCleanupService.class);
        urlService = mock(SheetFileUrlService.class);
        service = new GuitarSheetServiceImpl(daoFixture.sheetDao, daoFixture.fileDao, urlService,
                new SheetFileValidator(), ossUtilProvider, cleanupService, daoFixture.persistenceService);
    }

    @Test
    void uploadsPdfWithDerivedMimePersistsItAndReturnsOnlyPublicFileUrl() {
        when(ossUtilProvider.getIfAvailable()).thenReturn(ossUtil);
        when(ossUtil.upload(any(InputStream.class), anyLong(), anyString(), anyString(), anyString()))
                .thenReturn(upload("objects/a.pdf"));
        doAnswer(invocation -> {
            ((GuitarSheet) invocation.getArgument(0)).setId(7L);
            return null;
        }).when(daoFixture.persistenceService).persist(any(GuitarSheet.class), any());
        when(urlService.getFileUrl("objects/a.pdf")).thenReturn("https://cdn.example/a.pdf");

        SheetDetailResponse response = service.createSheet(3L, "Uploader", request(FileMode.PDF),
                Collections.singletonList(pdf("song.pdf")));

        assertThat(response.getId()).isEqualTo(7L);
        assertThat(response.getFiles()).singleElement().satisfies(file -> {
            assertThat(file.getUrl()).isEqualTo("https://cdn.example/a.pdf");
            assertThat(file.getMimeType()).isEqualTo("application/pdf");
        });
        ArgumentCaptor<String> filename = ArgumentCaptor.forClass(String.class);
        ArgumentCaptor<String> mime = ArgumentCaptor.forClass(String.class);
        ArgumentCaptor<String> directory = ArgumentCaptor.forClass(String.class);
        verify(ossUtil).upload(any(InputStream.class), eq(8L), filename.capture(), mime.capture(), directory.capture());
        assertThat(filename.getValue()).isEqualTo("sheet.pdf");
        assertThat(mime.getValue()).isEqualTo("application/pdf");
        assertThat(directory.getValue()).matches("love530/guitar/sheets/[0-9a-f-]{36}/pdf");
    }

    @Test
    void preservesImageOrderAndUsesGeneratedNamesAndDerivedMime() {
        when(ossUtilProvider.getIfAvailable()).thenReturn(ossUtil);
        when(ossUtil.upload(any(InputStream.class), anyLong(), anyString(), anyString(), anyString()))
                .thenReturn(upload("objects/one.jpg"), upload("objects/two.png"));
        doAnswer(invocation -> {
            ((GuitarSheet) invocation.getArgument(0)).setId(8L);
            return null;
        }).when(daoFixture.persistenceService).persist(any(GuitarSheet.class), any());
        when(urlService.getFileUrl(anyString())).thenReturn("https://cdn.example/file");

        SheetDetailResponse response = service.createSheet(3L, "Uploader", request(FileMode.IMAGES), Arrays.asList(
                image("first.jpg", new byte[]{(byte) 0xFF, (byte) 0xD8, (byte) 0xFF}),
                image("second.png", pngHeader())));

        assertThat(response.getFiles()).extracting(SheetDetailResponse.FileResponse::getSortOrder)
                .containsExactly(1, 2);
        ArgumentCaptor<String> filename = ArgumentCaptor.forClass(String.class);
        ArgumentCaptor<String> mime = ArgumentCaptor.forClass(String.class);
        verify(ossUtil, org.mockito.Mockito.times(2)).upload(any(InputStream.class), anyLong(), filename.capture(), mime.capture(), anyString());
        assertThat(filename.getAllValues()).containsExactly("image-01.jpg", "image-02.png");
        assertThat(mime.getAllValues()).containsExactly("image/jpeg", "image/png");
    }

    @Test
    void refusesUnavailableOssBeforePersistence() {
        when(ossUtilProvider.getIfAvailable()).thenReturn(null);

        assertApiError(() -> service.createSheet(3L, "Uploader", request(FileMode.PDF),
                Collections.singletonList(pdf("song.pdf"))), "OSS_UNAVAILABLE");

        verifyNoInteractions(daoFixture.persistenceService);
    }

    @Test
    void compensatesObjectsWhenLaterUploadOrPersistenceFails() {
        when(ossUtilProvider.getIfAvailable()).thenReturn(ossUtil);
        when(ossUtil.upload(any(InputStream.class), anyLong(), anyString(), anyString(), anyString()))
                .thenReturn(upload("objects/one.jpg"))
                .thenThrow(new IllegalStateException("OSS down"));

        assertApiError(() -> service.createSheet(3L, "Uploader", request(FileMode.IMAGES), Arrays.asList(
                image("first.jpg", new byte[]{(byte) 0xFF, (byte) 0xD8, (byte) 0xFF}),
                image("second.png", pngHeader()))), "OSS_UNAVAILABLE");
        verify(cleanupService).deleteOrEnqueue("objects/one.jpg", "SHEET_UPLOAD");
        verifyNoInteractions(daoFixture.persistenceService);

        when(ossUtil.upload(any(InputStream.class), anyLong(), anyString(), anyString(), anyString()))
                .thenReturn(upload("objects/a.pdf"));
        doThrow(new IllegalStateException("database failed")).when(daoFixture.persistenceService)
                .persist(any(GuitarSheet.class), any());
        assertThatThrownBy(() -> service.createSheet(3L, "Uploader", request(FileMode.PDF),
                Collections.singletonList(pdf("song.pdf")))).isInstanceOf(IllegalStateException.class);
        verify(cleanupService).deleteOrEnqueue("objects/a.pdf", "SHEET_UPLOAD");
    }

    @Test
    void rejectsInvalidMetadataBeforeOssAccess() {
        SheetSaveRequest request = request(FileMode.PDF);
        request.setSongName(" ");

        assertApiError(() -> service.createSheet(3L, "Uploader", request,
                Collections.singletonList(pdf("song.pdf"))), "SHEET_METADATA_INVALID");
        verify(ossUtilProvider, never()).getIfAvailable();
    }

    private SheetSaveRequest request(FileMode fileMode) {
        SheetSaveRequest request = new SheetSaveRequest();
        request.setSongName(" Song ");
        request.setSinger(" Singer ");
        request.setArranger("Arranger");
        request.setDescription("Description");
        request.setKeywords("keyword");
        request.setSheetType(SheetType.TAB);
        request.setDifficulty(SheetDifficulty.BEGINNER);
        request.setKeySignature("C");
        request.setCapoPosition(0);
        request.setTuning("Standard");
        request.setFileMode(fileMode);
        return request;
    }

    private MockMultipartFile pdf(String filename) {
        return new MockMultipartFile("files", filename, "image/png", "%PDF-1.7".getBytes(java.nio.charset.StandardCharsets.US_ASCII));
    }

    private MockMultipartFile image(String filename, byte[] bytes) {
        return new MockMultipartFile("files", filename, "application/octet-stream", bytes);
    }

    private OssUploadResult upload(String objectKey) {
        return new OssUploadResult("bucket", objectKey, "https://ignored", "etag", "ignored", 1L);
    }

    private byte[] pngHeader() {
        return new byte[]{(byte) 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A};
    }

    private void assertApiError(ThrowingCallable callable, String code) {
        assertThatThrownBy(callable::call).isInstanceOfSatisfying(GuitarApiException.class,
                exception -> assertThat(exception.getCode()).isEqualTo(code));
    }

    @SuppressWarnings("unchecked")
    private ObjectProvider<OssUtil> ossProvider() {
        return (ObjectProvider<OssUtil>) mock(ObjectProvider.class);
    }

    @FunctionalInterface
    private interface ThrowingCallable {
        void call();
    }

    private static final class GuitarSheetDaoFixture {
        private final com.example.guitar.sheet.dao.GuitarSheetDao sheetDao = mock(com.example.guitar.sheet.dao.GuitarSheetDao.class);
        private final com.example.guitar.sheet.dao.GuitarSheetFileDao fileDao = mock(com.example.guitar.sheet.dao.GuitarSheetFileDao.class);
        private final SheetUploadPersistenceService persistenceService = mock(SheetUploadPersistenceService.class);
    }
}
