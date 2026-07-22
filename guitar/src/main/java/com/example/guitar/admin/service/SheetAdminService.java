package com.example.guitar.admin.service;

import com.example.guitar.admin.dto.AdminSheetSearchRequest;
import com.example.guitar.admin.vo.AdminSheetSummaryResponse;

import java.util.List;

public interface SheetAdminService {

    AdminSheetSearchResult list(AdminSheetSearchRequest request);

    AdminSheetSummaryResponse offline(long adminUserId, long sheetId, String reason, String ipAddress);

    AdminSheetSummaryResponse restore(long adminUserId, long sheetId, String ipAddress);

    final class AdminSheetSearchResult {
        private final List<AdminSheetSummaryResponse> records;
        private final long total;
        private final int page;
        private final int size;

        public AdminSheetSearchResult(List<AdminSheetSummaryResponse> records, long total, int page, int size) {
            this.records = records;
            this.total = total;
            this.page = page;
            this.size = size;
        }

        public List<AdminSheetSummaryResponse> getRecords() { return records; }
        public long getTotal() { return total; }
        public int getPage() { return page; }
        public int getSize() { return size; }
    }
}
