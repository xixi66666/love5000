package com.example.guitar.sheet.service;

import com.example.guitar.sheet.dao.GuitarSheetDao;
import com.example.guitar.sheet.dao.GuitarSheetFileDao;
import com.example.guitar.sheet.model.GuitarSheet;
import com.example.guitar.sheet.model.GuitarSheetFile;
import com.example.guitar.web.GuitarApiException;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/** 数据库写入与远程 OSS 上传隔离，避免长事务占用连接。 */
@Service
public class SheetUploadPersistenceService {

    private final GuitarSheetDao sheetDao;
    private final GuitarSheetFileDao fileDao;

    public SheetUploadPersistenceService(GuitarSheetDao sheetDao, GuitarSheetFileDao fileDao) {
        this.sheetDao = sheetDao;
        this.fileDao = fileDao;
    }

    @Transactional
    public void persist(GuitarSheet sheet, List<GuitarSheetFile> files) {
        if (sheetDao.insert(sheet) != 1 || sheet.getId() == null || sheet.getId() < 1) {
            throw saveFailed();
        }
        for (GuitarSheetFile file : files) {
            file.setSheetId(sheet.getId());
        }
        if (fileDao.insertBatch(files) != files.size()) {
            throw saveFailed();
        }
    }

    private GuitarApiException saveFailed() {
        return new GuitarApiException(HttpStatus.INTERNAL_SERVER_ERROR,
                "SHEET_SAVE_FAILED", "曲谱保存失败，请稍后重试");
    }
}
