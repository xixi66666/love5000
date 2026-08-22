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
import com.example.guitar.storage.model.OssCleanupTask;
import com.example.guitar.web.GuitarApiException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.InOrder;
import org.mockito.ArgumentCaptor;
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
        GuitarSheetFile existing = file("existing.pdf", 1);
        when(sheetDao.findActiveByIdForOwner(8L, 5L)).thenReturn(offline);
        when(fileDao.findBySheetId(8L)).thenReturn(Collections.singletonList(existing));
        when(urlService.getFileUrl("existing.pdf")).thenReturn("https://cdn.example/existing.pdf");
        when(persistenceService.updateMetadata(eq(offline), any(SheetSaveRequest.class))).thenReturn(offline);

        GuitarSheetMutationService.MutationFiles result = service.update(5L, 8L, request(FileMode.PDF));

        assertThat(result.getSheet().getStatus()).isEqualTo("OFFLINE");
        verify(persistenceService).updateMetadata(eq(offline), any(SheetSaveRequest.class));
        verify(urlService).getFileUrl("existing.pdf");
        verifyNoInteractions(cleanupService);
        verify(ossProvider, never()).getIfAvailable();
    }

    @Test
    void metadataUrlFailurePreventsDatabaseCommit() {
        GuitarSheet current = sheet(8L, 5L, "PUBLISHED");
        when(sheetDao.findActiveByIdForOwner(8L, 5L)).thenReturn(current);
        when(fileDao.findBySheetId(8L)).thenReturn(Collections.singletonList(file("existing.pdf", 1)));
        when(urlService.getFileUrl("existing.pdf")).thenThrow(new IllegalStateException("url unavailable"));

        assertThatThrownBy(() -> service.update(5L, 8L, request(null)))
                .isInstanceOf(IllegalStateException.class);

        verifyNoInteractions(persistenceService);
    }

    @Test
    void metadataUpdateDoesNotRequireUnchangedFileMode() {
        GuitarSheet current = sheet(8L, 5L, "PUBLISHED");
        when(sheetDao.findActiveByIdForOwner(8L, 5L)).thenReturn(current);
        when(fileDao.findBySheetId(8L)).thenReturn(Collections.<GuitarSheetFile>emptyList());
        when(persistenceService.updateMetadata(eq(current), any(SheetSaveRequest.class))).thenReturn(current);

        GuitarSheetMutationService.MutationFiles result = service.update(5L, 8L, request(null));

        assertThat(result.getSheet()).isSameAs(current);
        verify(persistenceService).updateMetadata(eq(current), any(SheetSaveRequest.class));
    }

    @Test
    void nonOwnerCannotEditOrDeleteEvenWhenAdminRoleExistsElsewhere() {
        when(sheetDao.findActiveByIdForOwner(8L, 6L)).thenReturn(null);
        when(sheetDao.existsActiveById(8L)).thenReturn(1);

        assertApiError(() -> service.update(6L, 8L, request(FileMode.PDF)), "FORBIDDEN");
        assertApiError(() -> service.delete(6L, 8L), "FORBIDDEN");
        verifyNoInteractions(persistenceService, cleanupService);
    }

    @Test
    void ownershipIsCheckedBeforeMetadataOrFileValidation() {
        when(sheetDao.findActiveByIdForOwner(8L, 6L)).thenReturn(null);
        when(sheetDao.existsActiveById(8L)).thenReturn(1);

        assertApiError(() -> service.update(6L, 8L, null), "FORBIDDEN");
        assertApiError(() -> service.replaceFiles(6L, 8L, null, Collections.emptyList()), "FORBIDDEN");
        verifyNoInteractions(persistenceService, cleanupService, ossProvider);
    }

    @Test
    void missingOrDeletedSheetReturnsNotFound() {
        when(sheetDao.findActiveByIdForOwner(8L, 5L)).thenReturn(null);
        when(sheetDao.existsActiveById(8L)).thenReturn(0);

        assertApiError(() -> service.update(5L, 8L, request(FileMode.PDF)), "SHEET_NOT_FOUND");
        assertApiError(() -> service.delete(5L, 8L), "SHEET_NOT_FOUND");
    }

    @Test
    void replacementUploadsAndGeneratesUrlsBeforeDatabaseThenCleansOldObjectsAfterCommit() {
        GuitarSheet sheet = sheet(8L, 5L, "PUBLISHED");
        String oldKey = "love530/guitar/sheets/123e4567-e89b-12d3-a456-426614174000/pdf/sheet.pdf";
        GuitarSheetFile old = file(oldKey, 1);
        OssUtil oss = mock(OssUtil.class);
        when(sheetDao.findActiveByIdForOwner(8L, 5L)).thenReturn(sheet);
        when(fileDao.findBySheetId(8L)).thenReturn(Collections.singletonList(old));
        when(ossProvider.getIfAvailable()).thenReturn(oss);
        when(oss.uploadWithObjectKey(any(InputStream.class), anyLong(), anyString(), anyString(), anyString()))
                .thenAnswer(invocation -> new OssUploadResult("bucket", invocation.getArgument(2), "", "", "", 1L));
        when(urlService.getFileUrl(anyString())).thenReturn("https://cdn.example/new.pdf");
        when(persistenceService.replaceFiles(eq(sheet), eq("123e4567-e89b-12d3-a456-426614174000"),
                anyString(), eq(FileMode.PDF), any())).thenReturn(outbox(oldKey, "SHEET_REPLACE"));

        service.replaceFiles(5L, 8L, FileMode.PDF, Collections.singletonList(pdf()));

        ArgumentCaptor<String> keyCaptor = ArgumentCaptor.forClass(String.class);
        verify(oss).uploadWithObjectKey(any(InputStream.class), anyLong(), keyCaptor.capture(), anyString(), anyString());
        assertThat(keyCaptor.getValue())
                .matches("love530/guitar/sheets/[0-9a-f-]{36}/pdf/sheet\\.pdf")
                .isNotEqualTo(oldKey)
                .doesNotContain("123e4567-e89b-12d3-a456-426614174000");

        InOrder order = inOrder(oss, urlService, persistenceService, cleanupService);
        order.verify(oss).uploadWithObjectKey(any(InputStream.class), anyLong(), anyString(), anyString(), anyString());
        order.verify(urlService).getFileUrl(anyString());
        ArgumentCaptor<String> storageCaptor = ArgumentCaptor.forClass(String.class);
        order.verify(persistenceService).replaceFiles(eq(sheet), eq("123e4567-e89b-12d3-a456-426614174000"),
                storageCaptor.capture(), eq(FileMode.PDF), any());
        order.verify(cleanupService).deleteEnqueued(any(OssCleanupTask.class));
        assertThat(keyCaptor.getValue()).contains("/" + storageCaptor.getValue() + "/");
        assertThat(sheet.getStorageUuid()).isEqualTo(storageCaptor.getValue());
    }

    @Test
    void replacementVersionConflictCompensatesNewObjectsWithoutDeletingCommittedVersions() {
        GuitarSheet sheet = sheet(8L, 5L, "PUBLISHED");
        when(sheetDao.findActiveByIdForOwner(8L, 5L)).thenReturn(sheet);
        OssUtil oss = mock(OssUtil.class);
        when(ossProvider.getIfAvailable()).thenReturn(oss);
        when(oss.uploadWithObjectKey(any(InputStream.class), anyLong(), anyString(), anyString(), anyString()))
                .thenAnswer(invocation -> new OssUploadResult("bucket", invocation.getArgument(2), "", "", "", 1L));
        when(urlService.getFileUrl(anyString())).thenReturn("https://cdn.example/new.pdf");
        doThrow(new GuitarApiException(org.springframework.http.HttpStatus.CONFLICT,
                "SHEET_VERSION_CONFLICT", "曲谱文件已被其他请求更新，请刷新后重试")).when(persistenceService)
                .replaceFiles(any(), anyString(), anyString(), any(), any());

        assertThatThrownBy(() -> service.replaceFiles(5L, 8L, FileMode.PDF, Collections.singletonList(pdf())))
                .isInstanceOfSatisfying(GuitarApiException.class,
                        exception -> assertThat(exception.getCode()).isEqualTo("SHEET_VERSION_CONFLICT"));
        verify(cleanupService).deleteOrEnqueue(org.mockito.ArgumentMatchers.matches("love530/guitar/sheets/[0-9a-f-]{36}/pdf/sheet.pdf"),
                eq("SHEET_REPLACE_NEW"));
        verify(cleanupService, never()).deleteOrEnqueue("version-a.pdf", "SHEET_REPLACE");
        verify(cleanupService, never()).deleteOrEnqueue("version-b.pdf", "SHEET_REPLACE");
        verify(cleanupService, never()).deleteEnqueued(any());
    }

    @Test
    void replacementDeletedWhileUploadingReturnsNotFoundAndCompensatesNewObject() {
        GuitarSheet sheet = sheet(8L, 5L, "PUBLISHED");
        OssUtil oss = mock(OssUtil.class);
        when(sheetDao.findActiveByIdForOwner(8L, 5L)).thenReturn(sheet);
        when(ossProvider.getIfAvailable()).thenReturn(oss);
        when(oss.uploadWithObjectKey(any(InputStream.class), anyLong(), anyString(), anyString(), anyString()))
                .thenAnswer(invocation -> new OssUploadResult("bucket", invocation.getArgument(2), "", "", "", 1L));
        when(urlService.getFileUrl(anyString())).thenReturn("https://cdn.example/new.pdf");
        doThrow(new GuitarApiException(org.springframework.http.HttpStatus.NOT_FOUND,
                "SHEET_NOT_FOUND", "曲谱不存在或已删除")).when(persistenceService)
                .replaceFiles(any(), anyString(), anyString(), any(), any());

        assertThatThrownBy(() -> service.replaceFiles(5L, 8L, FileMode.PDF, Collections.singletonList(pdf())))
                .isInstanceOfSatisfying(GuitarApiException.class,
                        exception -> assertThat(exception.getCode()).isEqualTo("SHEET_NOT_FOUND"));
        verify(cleanupService).deleteOrEnqueue(
                org.mockito.ArgumentMatchers.matches("love530/guitar/sheets/[0-9a-f-]{36}/pdf/sheet.pdf"),
                eq("SHEET_REPLACE_NEW"));
    }

    @Test
    void uploadFailureKeepsOriginalCauseForDiagnostics() {
        GuitarSheet sheet = sheet(8L, 5L, "PUBLISHED");
        OssUtil oss = mock(OssUtil.class);
        IllegalStateException cause = new IllegalStateException("internal upload failure");
        when(sheetDao.findActiveByIdForOwner(8L, 5L)).thenReturn(sheet);
        when(ossProvider.getIfAvailable()).thenReturn(oss);
        when(oss.uploadWithObjectKey(any(InputStream.class), anyLong(), anyString(), anyString(), anyString()))
                .thenThrow(cause);

        assertThatThrownBy(() -> service.replaceFiles(5L, 8L, FileMode.PDF, Collections.singletonList(pdf())))
                .isInstanceOfSatisfying(GuitarApiException.class,
                        exception -> assertThat(exception.getCause()).isSameAs(cause));
    }

    @Test
    void deleteCleansFilesReturnedFromLockedTransactionInsteadOfStalePreTransactionSnapshot() {
        GuitarSheet sheet = sheet(8L, 5L, "PUBLISHED");
        when(sheetDao.findActiveByIdForOwner(8L, 5L)).thenReturn(sheet);
        when(fileDao.findBySheetId(8L)).thenReturn(Collections.singletonList(file("version-a.pdf", 1)));
        when(persistenceService.softDelete(sheet)).thenReturn(outbox("version-b.pdf", "SHEET_DELETE"));

        service.delete(5L, 8L);

        InOrder order = inOrder(persistenceService, cleanupService);
        order.verify(persistenceService).softDelete(eq(sheet));
        order.verify(cleanupService).deleteEnqueued(any(OssCleanupTask.class));
        verify(fileDao, never()).findBySheetId(8L);
        verify(cleanupService, never()).deleteOrEnqueue(anyString(), eq("SHEET_DELETE"));
    }

    @Test
    void postCommitCleanupFailureDoesNotRollBackOrFailDelete() {
        GuitarSheet sheet = sheet(8L, 5L, "PUBLISHED");
        when(sheetDao.findActiveByIdForOwner(8L, 5L)).thenReturn(sheet);
        SheetMutationPersistenceService.CleanupOutbox outbox = outbox("old.pdf", "SHEET_DELETE");
        when(persistenceService.softDelete(sheet)).thenReturn(outbox);
        doThrow(new IllegalStateException("database unavailable")).when(cleanupService)
                .deleteEnqueued(outbox.getTasks().get(0));

        service.delete(5L, 8L);

        verify(persistenceService).softDelete(sheet);
        verify(cleanupService).deleteEnqueued(outbox.getTasks().get(0));
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

    private SheetMutationPersistenceService.CleanupOutbox outbox(String objectKey, String businessType) {
        OssCleanupTask task = new OssCleanupTask();
        task.setId(77L); task.setObjectKey(objectKey); task.setBusinessType(businessType);
        task.setStatus("PENDING"); task.setRetryCount(0); task.setClaimVersion(0L);
        return new SheetMutationPersistenceService.CleanupOutbox(Collections.singletonList(task));
    }

    private void assertApiError(ThrowingCallable action, String code) {
        assertThatThrownBy(action::call).isInstanceOfSatisfying(GuitarApiException.class,
                exception -> assertThat(exception.getCode()).isEqualTo(code));
    }

    @SuppressWarnings("unchecked")
    private ObjectProvider<OssUtil> ossProvider() { return (ObjectProvider<OssUtil>) mock(ObjectProvider.class); }
    private interface ThrowingCallable { void call(); }
}
