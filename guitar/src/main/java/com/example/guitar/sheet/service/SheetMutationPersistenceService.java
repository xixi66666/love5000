package com.example.guitar.sheet.service;

import com.example.guitar.sheet.dao.GuitarSheetDao;
import com.example.guitar.sheet.dao.GuitarSheetFileDao;
import com.example.guitar.sheet.dto.SheetSaveRequest;
import com.example.guitar.sheet.model.FileMode;
import com.example.guitar.sheet.model.GuitarSheet;
import com.example.guitar.sheet.model.GuitarSheetFile;
import com.example.guitar.storage.dao.OssCleanupTaskDao;
import com.example.guitar.storage.model.OssCleanupTask;
import com.example.guitar.web.GuitarApiException;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Objects;

/** Owns short database transactions after remote file operations have succeeded. */
@Service
public class SheetMutationPersistenceService {
    private final GuitarSheetDao sheetDao;
    private final GuitarSheetFileDao fileDao;
    private final OssCleanupTaskDao cleanupTaskDao;

    public SheetMutationPersistenceService(GuitarSheetDao sheetDao, GuitarSheetFileDao fileDao,
                                           OssCleanupTaskDao cleanupTaskDao) {
        this.sheetDao = sheetDao;
        this.fileDao = fileDao;
        this.cleanupTaskDao = cleanupTaskDao;
    }

    @Transactional
    public GuitarSheet updateMetadata(GuitarSheet current, SheetSaveRequest request) {
        GuitarSheet locked = lock(current);
        if (!Objects.equals(locked.getStorageUuid(), current.getStorageUuid())) throw versionConflict();
        applyMetadata(locked, request);
        if (sheetDao.updateMetadata(locked) != 1) throw saveFailed();
        GuitarSheet reloaded = sheetDao.findActiveByIdForOwner(locked.getId(), locked.getUploaderId());
        if (reloaded == null) throw saveFailed();
        return reloaded;
    }

    @Transactional
    public CleanupOutbox replaceFiles(GuitarSheet current, String expectedStorageUuid, String newStorageUuid,
                                      FileMode mode, List<GuitarSheetFile> files) {
        GuitarSheet locked = lock(current);
        if (!Objects.equals(locked.getStorageUuid(), expectedStorageUuid)) throw versionConflict();
        List<GuitarSheetFile> oldFiles = fileDao.findBySheetId(locked.getId());
        locked.setStorageUuid(newStorageUuid);
        locked.setFileMode(mode.name());
        if (sheetDao.updateStorageAndFileMode(locked) != 1) throw saveFailed();
        fileDao.deleteBySheetId(locked.getId());
        for (GuitarSheetFile file : files) file.setSheetId(locked.getId());
        if (fileDao.insertBatch(files) != files.size()) throw saveFailed();
        return enqueueCleanup(oldFiles, "SHEET_REPLACE");
    }

    @Transactional
    public CleanupOutbox softDelete(GuitarSheet current) {
        GuitarSheet locked = lock(current);
        List<GuitarSheetFile> currentFiles = fileDao.findBySheetId(locked.getId());
        if (sheetDao.markDeleted(locked.getId(), locked.getUploaderId()) != 1) throw saveFailed();
        sheetDao.deleteFavoritesBySheetId(locked.getId());
        return enqueueCleanup(currentFiles, "SHEET_DELETE");
    }

    private CleanupOutbox enqueueCleanup(List<GuitarSheetFile> files, String businessType) {
        if (files == null || files.isEmpty()) return new CleanupOutbox(Collections.<OssCleanupTask>emptyList());
        List<OssCleanupTask> tasks = new ArrayList<OssCleanupTask>();
        LocalDateTime now = LocalDateTime.now();
        for (GuitarSheetFile file : files) {
            OssCleanupTask task = new OssCleanupTask();
            task.setObjectKey(file.getObjectKey());
            task.setBusinessType(businessType);
            task.setStatus("PENDING");
            task.setRetryCount(0);
            task.setNextRetryAt(now);
            task.setClaimVersion(0L);
            if (cleanupTaskDao.insertPending(task) != 1 || task.getId() == null) throw saveFailed();
            tasks.add(task);
        }
        return new CleanupOutbox(tasks);
    }

    private void applyMetadata(GuitarSheet target, SheetSaveRequest source) {
        target.setSongName(source.getSongName()); target.setSinger(source.getSinger()); target.setArranger(source.getArranger());
        target.setDescription(source.getDescription()); target.setKeywords(source.getKeywords());
        target.setSheetType(source.getSheetType().name()); target.setDifficulty(source.getDifficulty().name());
        target.setKeySignature(source.getKeySignature()); target.setCapoPosition(source.getCapoPosition()); target.setTuning(source.getTuning());
    }

    private GuitarSheet lock(GuitarSheet current) {
        GuitarSheet locked = sheetDao.findActiveByIdForOwnerForUpdate(current.getId(), current.getUploaderId());
        if (locked == null) throw notFound();
        return locked;
    }

    private GuitarApiException saveFailed() {
        return new GuitarApiException(HttpStatus.INTERNAL_SERVER_ERROR, "SHEET_SAVE_FAILED", "曲谱保存失败，请稍后重试");
    }

    private GuitarApiException versionConflict() {
        return new GuitarApiException(HttpStatus.CONFLICT, "SHEET_VERSION_CONFLICT", "曲谱文件已被其他请求更新，请刷新后重试");
    }

    private GuitarApiException notFound() {
        return new GuitarApiException(HttpStatus.NOT_FOUND, "SHEET_NOT_FOUND", "曲谱不存在或已删除");
    }

    public static final class CleanupOutbox {
        private final List<OssCleanupTask> tasks;

        CleanupOutbox(List<OssCleanupTask> tasks) {
            this.tasks = Collections.unmodifiableList(new ArrayList<OssCleanupTask>(tasks));
        }

        public List<OssCleanupTask> getTasks() { return tasks; }
    }
}
