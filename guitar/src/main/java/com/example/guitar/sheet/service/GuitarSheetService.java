package com.example.guitar.sheet.service;

import com.example.guitar.sheet.dto.SheetSearchRequest;
import com.example.guitar.sheet.dto.SheetSaveRequest;
import com.example.guitar.sheet.model.FileMode;
import com.example.guitar.sheet.vo.SheetDetailResponse;
import com.example.guitar.sheet.vo.SheetSummaryResponse;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

public interface GuitarSheetService {

    SheetSearchResult searchPublicSheets(SheetSearchRequest request);

    SheetDetailResponse getPublicSheetDetail(Long id);

    SheetDetailResponse createSheet(Long uploaderId, String uploaderNickname,
                                    SheetSaveRequest request, List<MultipartFile> files);

    SheetDetailResponse update(long userId, long sheetId, SheetSaveRequest request);

    SheetDetailResponse replaceFiles(long userId, long sheetId, FileMode mode, List<MultipartFile> files);

    void delete(long userId, long sheetId);

    final class SheetSearchResult {
        private final List<SheetSummaryResponse> records;
        private final long total;
        private final int page;
        private final int size;

        public SheetSearchResult(List<SheetSummaryResponse> records, long total, int page, int size) {
            this.records = records;
            this.total = total;
            this.page = page;
            this.size = size;
        }

        public List<SheetSummaryResponse> getRecords() { return records; }
        public long getTotal() { return total; }
        public int getPage() { return page; }
        public int getSize() { return size; }
    }
}
