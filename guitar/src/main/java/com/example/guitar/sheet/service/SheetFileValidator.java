package com.example.guitar.sheet.service;

import com.example.guitar.sheet.model.FileMode;
import com.example.guitar.web.GuitarApiException;
import org.springframework.http.HttpStatus;

public class SheetFileValidator {

    public FileMode requireFileMode(FileMode fileMode) {
        if (fileMode == null) {
            throw invalidMetadata();
        }
        return fileMode;
    }

    public void validateFileModeBoundary(FileMode fileMode, int fileCount) {
        requireFileMode(fileMode);
        if (fileCount < 0 || (fileMode == FileMode.SINGLE && fileCount > 1)) {
            throw invalidMetadata();
        }
    }

    private GuitarApiException invalidMetadata() {
        return new GuitarApiException(HttpStatus.BAD_REQUEST, "SHEET_METADATA_INVALID", "曲谱元数据不正确");
    }
}
