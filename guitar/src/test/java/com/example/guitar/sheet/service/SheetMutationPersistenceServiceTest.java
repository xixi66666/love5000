package com.example.guitar.sheet.service;

import com.example.guitar.sheet.dao.GuitarSheetDao;
import com.example.guitar.sheet.dao.GuitarSheetFileDao;
import com.example.guitar.sheet.model.FileMode;
import com.example.guitar.sheet.dto.SheetSaveRequest;
import com.example.guitar.sheet.model.GuitarSheet;
import com.example.guitar.sheet.model.GuitarSheetFile;
import com.example.guitar.storage.dao.OssCleanupTaskDao;
import com.example.guitar.storage.model.OssCleanupTask;
import com.example.guitar.web.GuitarApiException;
import org.junit.jupiter.api.Test;
import org.mockito.InOrder;

import java.util.Collections;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class SheetMutationPersistenceServiceTest {

    @Test
    void fileReplacementAtomicallySwitchesStorageAndFilesWithoutChangingMetadataOrStatus() {
        GuitarSheetDao sheetDao = mock(GuitarSheetDao.class);
        GuitarSheetFileDao fileDao = mock(GuitarSheetFileDao.class);
        OssCleanupTaskDao cleanupTaskDao = cleanupTaskDao();
        SheetMutationPersistenceService service = new SheetMutationPersistenceService(sheetDao, fileDao, cleanupTaskDao);
        GuitarSheet current = sheet("old-storage");
        GuitarSheet locked = sheet("old-storage");
        GuitarSheetFile replacement = new GuitarSheetFile();
        replacement.setObjectKey("love530/guitar/sheets/new-storage/images/image-01.png");
        when(sheetDao.findActiveByIdForOwnerForUpdate(8L, 5L)).thenReturn(locked);
        GuitarSheetFile oldFile = new GuitarSheetFile();
        oldFile.setObjectKey("love530/guitar/sheets/old-storage/pdf/sheet.pdf");
        when(fileDao.findBySheetId(8L)).thenReturn(Collections.singletonList(oldFile));
        when(sheetDao.updateStorageAndFileMode(any())).thenReturn(1);
        when(fileDao.insertBatch(any())).thenReturn(1);

        SheetMutationPersistenceService.CleanupOutbox result = service.replaceFiles(
                current, "old-storage", "new-storage", FileMode.IMAGES,
                Collections.singletonList(replacement));

        assertThat(locked.getStorageUuid()).isEqualTo("new-storage");
        assertThat(locked.getFileMode()).isEqualTo("IMAGES");
        assertThat(locked.getStatus()).isEqualTo("OFFLINE");
        assertThat(locked.getSongName()).isEqualTo("Original Song");
        assertThat(replacement.getSheetId()).isEqualTo(8L);
        assertThat(result.getTasks()).singleElement().satisfies(task -> {
            assertThat(task.getId()).isEqualTo(100L);
            assertThat(task.getObjectKey()).isEqualTo(oldFile.getObjectKey());
            assertThat(task.getBusinessType()).isEqualTo("SHEET_REPLACE");
            assertThat(task.getStatus()).isEqualTo("PENDING");
        });
        InOrder order = inOrder(sheetDao, fileDao, cleanupTaskDao);
        order.verify(sheetDao).findActiveByIdForOwnerForUpdate(8L, 5L);
        order.verify(fileDao).findBySheetId(8L);
        order.verify(sheetDao).updateStorageAndFileMode(locked);
        order.verify(fileDao).deleteBySheetId(8L);
        order.verify(fileDao).insertBatch(Collections.singletonList(replacement));
        order.verify(cleanupTaskDao).insertPending(any(OssCleanupTask.class));
    }

    @Test
    void fileReplacementRejectsStaleStorageVersionBeforeChangingDatabaseRows() {
        GuitarSheetDao sheetDao = mock(GuitarSheetDao.class);
        GuitarSheetFileDao fileDao = mock(GuitarSheetFileDao.class);
        OssCleanupTaskDao cleanupTaskDao = cleanupTaskDao();
        SheetMutationPersistenceService service = new SheetMutationPersistenceService(sheetDao, fileDao, cleanupTaskDao);
        GuitarSheet current = sheet("version-a");
        GuitarSheet locked = sheet("version-b");
        GuitarSheetFile replacement = new GuitarSheetFile();
        replacement.setObjectKey("love530/guitar/sheets/version-c/pdf/sheet.pdf");
        when(sheetDao.findActiveByIdForOwnerForUpdate(8L, 5L)).thenReturn(locked);

        assertThatThrownBy(() -> service.replaceFiles(current, "version-a", "version-c", FileMode.PDF,
                Collections.singletonList(replacement)))
                .isInstanceOfSatisfying(GuitarApiException.class,
                        exception -> {
                            assertThat(exception.getStatus()).isEqualTo(org.springframework.http.HttpStatus.CONFLICT);
                            assertThat(exception.getCode()).isEqualTo("SHEET_VERSION_CONFLICT");
                        });

        verify(sheetDao, never()).updateStorageAndFileMode(any());
        verify(fileDao, never()).deleteBySheetId(any());
        verify(fileDao, never()).insertBatch(any());
        verify(cleanupTaskDao, never()).insertPending(any());
        assertThat(locked.getStorageUuid()).isEqualTo("version-b");
    }

    @Test
    void metadataUpdateRejectsFilesChangedAfterUrlSnapshot() {
        GuitarSheetDao sheetDao = mock(GuitarSheetDao.class);
        GuitarSheetFileDao fileDao = mock(GuitarSheetFileDao.class);
        OssCleanupTaskDao cleanupTaskDao = cleanupTaskDao();
        SheetMutationPersistenceService service = new SheetMutationPersistenceService(sheetDao, fileDao, cleanupTaskDao);
        GuitarSheet current = sheet("version-a");
        GuitarSheet locked = sheet("version-b");
        when(sheetDao.findActiveByIdForOwnerForUpdate(8L, 5L)).thenReturn(locked);

        assertThatThrownBy(() -> service.updateMetadata(current, new SheetSaveRequest()))
                .isInstanceOfSatisfying(GuitarApiException.class,
                        exception -> assertThat(exception.getCode()).isEqualTo("SHEET_VERSION_CONFLICT"));

        verify(sheetDao, never()).updateMetadata(any());
    }

    @Test
    void softDeleteReadsCurrentFilesAfterLockBeforeDeletingFavorites() {
        GuitarSheetDao sheetDao = mock(GuitarSheetDao.class);
        GuitarSheetFileDao fileDao = mock(GuitarSheetFileDao.class);
        OssCleanupTaskDao cleanupTaskDao = cleanupTaskDao();
        SheetMutationPersistenceService service = new SheetMutationPersistenceService(sheetDao, fileDao, cleanupTaskDao);
        GuitarSheet current = sheet("version-a");
        GuitarSheet locked = sheet("version-b");
        GuitarSheetFile currentFile = new GuitarSheetFile();
        currentFile.setObjectKey("love530/guitar/sheets/version-b/pdf/sheet.pdf");
        when(sheetDao.findActiveByIdForOwnerForUpdate(8L, 5L)).thenReturn(locked);
        when(fileDao.findBySheetId(8L)).thenReturn(Collections.singletonList(currentFile));
        when(sheetDao.markDeleted(8L, 5L)).thenReturn(1);

        assertThat(service.softDelete(current).getTasks()).singleElement()
                .extracting(OssCleanupTask::getObjectKey).isEqualTo(currentFile.getObjectKey());

        InOrder order = inOrder(sheetDao, fileDao);
        order.verify(sheetDao).findActiveByIdForOwnerForUpdate(8L, 5L);
        order.verify(fileDao).findBySheetId(8L);
        order.verify(sheetDao).markDeleted(8L, 5L);
        order.verify(sheetDao).deleteFavoritesBySheetId(8L);
    }

    @Test
    void lockMissingReturnsStableNotFoundInsteadOfInternalError() {
        GuitarSheetDao sheetDao = mock(GuitarSheetDao.class);
        GuitarSheetFileDao fileDao = mock(GuitarSheetFileDao.class);
        OssCleanupTaskDao cleanupTaskDao = cleanupTaskDao();
        SheetMutationPersistenceService service = new SheetMutationPersistenceService(sheetDao, fileDao, cleanupTaskDao);
        GuitarSheet current = sheet("version-a");
        when(sheetDao.findActiveByIdForOwnerForUpdate(8L, 5L)).thenReturn(null);

        assertThatThrownBy(() -> service.softDelete(current))
                .isInstanceOfSatisfying(GuitarApiException.class,
                        exception -> {
                            assertThat(exception.getStatus()).isEqualTo(org.springframework.http.HttpStatus.NOT_FOUND);
                            assertThat(exception.getCode()).isEqualTo("SHEET_NOT_FOUND");
                        });
    }

    @Test
    void softDeleteDoesNotDependOnRedundantFavoriteCountReset() {
        GuitarSheetDao sheetDao = mock(GuitarSheetDao.class);
        GuitarSheetFileDao fileDao = mock(GuitarSheetFileDao.class);
        OssCleanupTaskDao cleanupTaskDao = cleanupTaskDao();
        SheetMutationPersistenceService service = new SheetMutationPersistenceService(sheetDao, fileDao, cleanupTaskDao);
        GuitarSheet current = sheet("version-a");
        when(sheetDao.findActiveByIdForOwnerForUpdate(8L, 5L)).thenReturn(current);
        when(fileDao.findBySheetId(8L)).thenReturn(Collections.<GuitarSheetFile>emptyList());
        when(sheetDao.markDeleted(8L, 5L)).thenReturn(1);
        assertThat(service.softDelete(current).getTasks()).isEmpty();

        verify(sheetDao).deleteFavoritesBySheetId(8L);
    }

    private GuitarSheet sheet(String storageUuid) {
        GuitarSheet sheet = new GuitarSheet();
        sheet.setId(8L);
        sheet.setUploaderId(5L);
        sheet.setSongName("Original Song");
        sheet.setStatus("OFFLINE");
        sheet.setFileMode("PDF");
        sheet.setStorageUuid(storageUuid);
        return sheet;
    }

    private OssCleanupTaskDao cleanupTaskDao() {
        OssCleanupTaskDao dao = mock(OssCleanupTaskDao.class);
        when(dao.insertPending(any(OssCleanupTask.class))).thenAnswer(invocation -> {
            OssCleanupTask task = invocation.getArgument(0);
            task.setId(100L);
            return 1;
        });
        return dao;
    }
}
