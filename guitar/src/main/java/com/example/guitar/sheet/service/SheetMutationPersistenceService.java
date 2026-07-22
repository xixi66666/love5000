package com.example.guitar.sheet.service;

import com.example.guitar.sheet.dao.GuitarSheetDao;
import com.example.guitar.sheet.dao.GuitarSheetFileDao;
import com.example.guitar.sheet.dto.SheetSaveRequest;
import com.example.guitar.sheet.model.FileMode;
import com.example.guitar.sheet.model.GuitarSheet;
import com.example.guitar.sheet.model.GuitarSheetFile;
import com.example.guitar.web.GuitarApiException;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/** Owns short database transactions after remote file operations have succeeded. */
@Service
public class SheetMutationPersistenceService {
    private final GuitarSheetDao sheetDao;
    private final GuitarSheetFileDao fileDao;

    public SheetMutationPersistenceService(GuitarSheetDao sheetDao, GuitarSheetFileDao fileDao) {
        this.sheetDao = sheetDao;
        this.fileDao = fileDao;
    }

    @Transactional
    public GuitarSheet updateMetadata(GuitarSheet current, SheetSaveRequest request) {
        GuitarSheet locked = lock(current);
        applyMetadata(locked, request);
        if (sheetDao.updateMetadata(locked) != 1) throw saveFailed();
        GuitarSheet reloaded = sheetDao.findActiveByIdForOwner(locked.getId(), locked.getUploaderId());
        if (reloaded == null) throw saveFailed();
        return reloaded;
    }

    @Transactional
    public void replaceFiles(GuitarSheet current, String newStorageUuid, FileMode mode,
                             List<GuitarSheetFile> files) {
        GuitarSheet locked = lock(current);
        locked.setStorageUuid(newStorageUuid);
        locked.setFileMode(mode.name());
        if (sheetDao.updateStorageAndFileMode(locked) != 1) throw saveFailed();
        fileDao.deleteBySheetId(locked.getId());
        for (GuitarSheetFile file : files) file.setSheetId(locked.getId());
        if (fileDao.insertBatch(files) != files.size()) throw saveFailed();
    }

    @Transactional
    public void softDelete(GuitarSheet current) {
        GuitarSheet locked = lock(current);
        if (sheetDao.markDeleted(locked.getId(), locked.getUploaderId()) != 1) throw saveFailed();
        sheetDao.deleteFavoritesBySheetId(locked.getId());
        if (sheetDao.resetFavoriteCount(locked.getId()) != 1) throw saveFailed();
    }

    private void applyMetadata(GuitarSheet target, SheetSaveRequest source) {
        target.setSongName(source.getSongName()); target.setSinger(source.getSinger()); target.setArranger(source.getArranger());
        target.setDescription(source.getDescription()); target.setKeywords(source.getKeywords());
        target.setSheetType(source.getSheetType().name()); target.setDifficulty(source.getDifficulty().name());
        target.setKeySignature(source.getKeySignature()); target.setCapoPosition(source.getCapoPosition()); target.setTuning(source.getTuning());
    }

    private GuitarSheet lock(GuitarSheet current) {
        GuitarSheet locked = sheetDao.findActiveByIdForOwnerForUpdate(current.getId(), current.getUploaderId());
        if (locked == null) throw saveFailed();
        return locked;
    }

    private GuitarApiException saveFailed() {
        return new GuitarApiException(HttpStatus.INTERNAL_SERVER_ERROR, "SHEET_SAVE_FAILED", "曲谱保存失败，请稍后重试");
    }
}
