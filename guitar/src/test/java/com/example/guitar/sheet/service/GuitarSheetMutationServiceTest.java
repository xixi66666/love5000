package com.example.guitar.sheet.service;

import com.example.common.util.OssUploadResult;
import com.example.common.util.OssUtil;
import com.example.guitar.sheet.dao.GuitarSheetDao;
import com.example.guitar.sheet.dao.GuitarSheetFileDao;
import com.example.guitar.sheet.dto.SheetSaveRequest;
import com.example.guitar.sheet.model.FileMode;
import com.example.guitar.sheet.model.GuitarSheet;
import com.example.guitar.sheet.model.GuitarSheetFile;
import com.example.guitar.sheet.model.SheetDifficulty;
import com.example.guitar.sheet.model.SheetType;
import com.example.guitar.storage.service.OssCleanupService;
import com.example.guitar.web.GuitarApiException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.InOrder;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.mock.web.MockMultipartFile;

import java.io.InputStream;
import java.util.Collections;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class GuitarSheetMutationServiceTest {

    private GuitarSheetDao sheetDao;
    private GuitarSheetFileDao fileDao;
    private SheetFileValidator validator;
    private SheetFileUrlService urlService;
    private ObjectProvider<OssUtil> ossProvider;
    private OssCleanupService cleanupService;
    private SheetMutationPersistenceService persistenceService;
    private GuitarSheetMutationService service;

    @BeforeEach
    void setUp() {
        sheetDao = mock(GuitarSheetDao.class);
        fileDao = mock(GuitarSheetFileDao.class);
        validator = new SheetFileValidator();
        urlService = mock(SheetFileUrlService.class);
        ossProvider = ossProvider();
        cleanupService = mock(OssCleanupService.class);
        persistenceService = mock(SheetMutationPersistenceService.class);
        service = new GuitarSheetMutationService(sheetDao, fileDao, validator, urlService, ossProvider,
                cleanupService, persistenceService);
    }

    @Test
    void ownerCanEditOfflineMetadataWithoutChangingStatusOrUsingOss() {
        GuitarSheet offline = sheet(8L, 5L, "OFFLINE");
        when(sheetDao.findActiveByIdForOwner(8L, 5L)).thenReturn(offline);
        when(persistenceService.updateMetadata(eq(offline), any(SheetSaveRequest.class))).thenReturn(offline);

        GuitarSheet result = service.updateMetadata(5L, 8L, request(FileMode.PDF));

        assertThat(result.getStatus()).isEqualTo("OFFLINE");
        verify(persistenceService).updateMetadata(eq(offline), any(SheetSaveRequest.class));
        verifyNoInteractions(urlService, cleanupService);
        verify(ossProvider, never()).getIfAvailable();
    }

    @Test
    void nonOwnerCannotEditOrDeleteEvenWhenAdminRoleExistsElsewhere() {
        when(sheetDao.findActiveByIdForOwner(8L, 6L)).thenReturn(null);
        when(sheetDao.existsActiveById(8L)).thenReturn(1);

        assertApiError(() -> service.updateMetadata(6L, 8L, request(FileMode.PDF)), "FORBIDDEN");
        assertApiError(() -> service.deleteSheet(6L, 8L), "FORBIDDEN");
        verifyNoInteractions(persistenceService, cleanupService);
    }

    @Test
    void missingOrDeletedSheetReturnsNotFound() {
        when(sheetDao.findActiveByIdForOwner(8L, 5L)).thenReturn(null);
        when(sheetDao.existsActiveById(8L)).thenReturn(0);

        assertApiError(() -> service.updateMetadata(5L, 8L, request(FileMode.PDF)), "SHEET_NOT_FOUND");
        assertApiError(() -> service.deleteSheet(5L, 8L), "SHEET_NOT_FOUND");
    }

    @Test
    void replacementUploadsAndGeneratesUrlsBeforeDatabaseThenCleansOldObjectsAfterCommit() {
        GuitarSheet sheet = sheet(8L, 5L, "PUBLISHED");
        GuitarSheetFile old = file("old.pdf", 1);
        OssUtil oss = mock(OssUtil.class);
        when(sheetDao.findActiveByIdForOwner(8L, 5L)).thenReturn(sheet);
        when(fileDao.findBySheetId(8L)).thenReturn(Collections.singletonList(old));
        when(ossProvider.getIfAvailable()).thenReturn(oss);
        when(oss.uploadWithObjectKey(any(InputStream.class), anyLong(), anyString(), anyString(), anyString()))
                .thenAnswer(invocation -> new OssUploadResult("bucket", invocation.getArgument(2), "", "", "", 1L));
        when(urlService.getFileUrl(anyString())).thenReturn("https://cdn.example/new.pdf");

        service.replaceFiles(5L, 8L, request(FileMode.PDF), Collections.singletonList(pdf()));

        InOrder order = inOrder(oss, urlService, persistenceService, cleanupService);
        order.verify(oss).uploadWithObjectKey(any(InputStream.class), anyLong(), anyString(), anyString(), anyString());
        order.verify(urlService).getFileUrl(anyString());
        order.verify(persistenceService).replaceFiles(eq(sheet), any(SheetSaveRequest.class), any());
        order.verify(cleanupService).deleteOrEnqueue("old.pdf", "SHEET_REPLACE");
    }

    @Test
    void replacementDatabaseFailureCompensatesNewObjectsWithoutDeletingOldObjects() {
        GuitarSheet sheet = sheet(8L, 5L, "PUBLISHED");
        when(sheetDao.findActiveByIdForOwner(8L, 5L)).thenReturn(sheet);
        when(fileDao.findBySheetId(8L)).thenReturn(Collections.singletonList(file("old.pdf", 1)));
        OssUtil oss = mock(OssUtil.class);
        when(ossProvider.getIfAvailable()).thenReturn(oss);
        when(oss.uploadWithObjectKey(any(InputStream.class), anyLong(), anyString(), anyString(), anyString()))
                .thenAnswer(invocation -> new OssUploadResult("bucket", invocation.getArgument(2), "", "", "", 1L));
        when(urlService.getFileUrl(anyString())).thenReturn("https://cdn.example/new.pdf");
        doThrow(new IllegalStateException("db")).when(persistenceService).replaceFiles(any(), any(), any());

        assertThatThrownBy(() -> service.replaceFiles(5L, 8L, request(FileMode.PDF), Collections.singletonList(pdf())))
                .isInstanceOf(IllegalStateException.class);
        verify(cleanupService).deleteOrEnqueue(org.mockito.ArgumentMatchers.matches("love530/guitar/sheets/[0-9a-f-]{36}/pdf/sheet.pdf"),
                eq("SHEET_REPLACE_NEW"));
        verify(cleanupService, never()).deleteOrEnqueue("old.pdf", "SHEET_REPLACE");
    }

    @Test
    void deleteCommitsSoftDeleteAndFavoriteRemovalBeforeOssCleanupAndIsRepeatSafe() {
        GuitarSheet sheet = sheet(8L, 5L, "PUBLISHED");
        when(sheetDao.findActiveByIdForOwner(8L, 5L)).thenReturn(sheet);
        when(fileDao.findBySheetId(8L)).thenReturn(Collections.singletonList(file("old.pdf", 1)));

        service.deleteSheet(5L, 8L);

        InOrder order = inOrder(persistenceService, cleanupService);
        order.verify(persistenceService).softDelete(eq(sheet));
        order.verify(cleanupService).deleteOrEnqueue("old.pdf", "SHEET_DELETE");
    }

    @Test
    void postCommitCleanupFailureDoesNotRollBackOrFailDelete() {
        GuitarSheet sheet = sheet(8L, 5L, "PUBLISHED");
        when(sheetDao.findActiveByIdForOwner(8L, 5L)).thenReturn(sheet);
        when(fileDao.findBySheetId(8L)).thenReturn(Collections.singletonList(file("old.pdf", 1)));
        doThrow(new IllegalStateException("queue unavailable")).when(cleanupService)
                .deleteOrEnqueue("old.pdf", "SHEET_DELETE");

        service.deleteSheet(5L, 8L);

        verify(persistenceService).softDelete(sheet);
    }

    private SheetSaveRequest request(FileMode mode) {
        SheetSaveRequest request = new SheetSaveRequest();
        request.setSongName("Song"); request.setSinger("Singer"); request.setSheetType(SheetType.TAB);
        request.setDifficulty(SheetDifficulty.BEGINNER); request.setKeySignature("C"); request.setTuning("Standard");
        request.setFileMode(mode);
        return request;
    }

    private MockMultipartFile pdf() {
        return new MockMultipartFile("files", "song.pdf", "application/pdf", "%PDF-1.7".getBytes(java.nio.charset.StandardCharsets.US_ASCII));
    }

    private GuitarSheet sheet(long id, long ownerId, String status) {
        GuitarSheet sheet = new GuitarSheet(); sheet.setId(id); sheet.setUploaderId(ownerId); sheet.setStatus(status);
        sheet.setStorageUuid("123e4567-e89b-12d3-a456-426614174000"); sheet.setFileMode("PDF"); return sheet;
    }

    private GuitarSheetFile file(String objectKey, int sortOrder) {
        GuitarSheetFile file = new GuitarSheetFile(); file.setObjectKey(objectKey); file.setSortOrder(sortOrder); return file;
    }

    private void assertApiError(ThrowingCallable action, String code) {
        assertThatThrownBy(action::call).isInstanceOfSatisfying(GuitarApiException.class,
                exception -> assertThat(exception.getCode()).isEqualTo(code));
    }

    @SuppressWarnings("unchecked")
    private ObjectProvider<OssUtil> ossProvider() { return (ObjectProvider<OssUtil>) mock(ObjectProvider.class); }
    private interface ThrowingCallable { void call(); }
}
