package com.example.guitar.sheet.service;

import com.example.guitar.sheet.dao.GuitarSheetDao;
import com.example.guitar.sheet.dao.GuitarSheetFileDao;
import com.example.guitar.sheet.model.FileMode;
import com.example.guitar.sheet.model.GuitarSheet;
import com.example.guitar.sheet.model.GuitarSheetFile;
import org.junit.jupiter.api.Test;
import org.mockito.InOrder;

import java.util.Collections;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class SheetMutationPersistenceServiceTest {

    @Test
    void fileReplacementAtomicallySwitchesStorageAndFilesWithoutChangingMetadataOrStatus() {
        GuitarSheetDao sheetDao = mock(GuitarSheetDao.class);
        GuitarSheetFileDao fileDao = mock(GuitarSheetFileDao.class);
        SheetMutationPersistenceService service = new SheetMutationPersistenceService(sheetDao, fileDao);
        GuitarSheet current = sheet("old-storage");
        GuitarSheet locked = sheet("old-storage");
        GuitarSheetFile replacement = new GuitarSheetFile();
        replacement.setObjectKey("love530/guitar/sheets/new-storage/images/image-01.png");
        when(sheetDao.findActiveByIdForOwnerForUpdate(8L, 5L)).thenReturn(locked);
        when(sheetDao.updateStorageAndFileMode(any())).thenReturn(1);
        when(fileDao.insertBatch(any())).thenReturn(1);

        service.replaceFiles(current, "new-storage", FileMode.IMAGES, Collections.singletonList(replacement));

        assertThat(locked.getStorageUuid()).isEqualTo("new-storage");
        assertThat(locked.getFileMode()).isEqualTo("IMAGES");
        assertThat(locked.getStatus()).isEqualTo("OFFLINE");
        assertThat(locked.getSongName()).isEqualTo("Original Song");
        assertThat(replacement.getSheetId()).isEqualTo(8L);
        InOrder order = inOrder(sheetDao, fileDao);
        order.verify(sheetDao).findActiveByIdForOwnerForUpdate(8L, 5L);
        order.verify(sheetDao).updateStorageAndFileMode(locked);
        order.verify(fileDao).deleteBySheetId(8L);
        order.verify(fileDao).insertBatch(Collections.singletonList(replacement));
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
}
