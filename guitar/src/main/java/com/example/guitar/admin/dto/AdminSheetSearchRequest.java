package com.example.guitar.admin.dto;

import com.example.guitar.sheet.model.SheetStatus;
import com.example.guitar.web.GuitarApiException;
import org.springframework.http.HttpStatus;

import java.util.Locale;

public class AdminSheetSearchRequest {

    private static final int MAX_KEYWORD_LENGTH = 120;
    private static final long MAX_OFFSET = 5_000_000L;

    public enum Sort {
        LATEST,
        MOST_FAVORITED,
        MOST_VIEWED
    }

    private String keyword;
    private String status;
    private String sort;
    private Integer page;
    private Integer size;
    private String keywordLike;
    private long offset;

    public void normalizeAndValidate() {
        keyword = trimToNull(keyword);
        status = normalizeEnum(status, SheetStatus.class);
        sort = normalizeEnum(sort == null ? Sort.LATEST.name() : sort, Sort.class);
        page = page == null ? 1 : page;
        size = size == null ? 20 : size;
        if ((keyword != null && keyword.length() > MAX_KEYWORD_LENGTH)
                || page < 1 || size < 1 || size > 50) {
            throw validationError();
        }
        offset = ((long) page - 1L) * size;
        if (offset > MAX_OFFSET) {
            throw new GuitarApiException(HttpStatus.BAD_REQUEST, "PAGE_TOO_LARGE", "页码超出管理员查询范围");
        }
        keywordLike = toLikePattern(keyword);
    }

    private <T extends Enum<T>> String normalizeEnum(String value, Class<T> type) {
        String normalized = trimToNull(value);
        if (normalized == null) {
            return null;
        }
        try {
            return Enum.valueOf(type, normalized.toUpperCase(Locale.ROOT)).name();
        } catch (IllegalArgumentException exception) {
            throw validationError();
        }
    }

    private String trimToNull(String value) {
        if (value == null) {
            return null;
        }
        String trimmed = value.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }

    private String toLikePattern(String value) {
        if (value == null) {
            return null;
        }
        return "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%";
    }

    private GuitarApiException validationError() {
        return new GuitarApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", "管理员曲谱查询参数不正确");
    }

    public String getKeyword() { return keyword; }
    public void setKeyword(String keyword) { this.keyword = keyword; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getSort() { return sort; }
    public void setSort(String sort) { this.sort = sort; }
    public Integer getPage() { return page; }
    public void setPage(Integer page) { this.page = page; }
    public Integer getSize() { return size; }
    public void setSize(Integer size) { this.size = size; }
    public String getKeywordLike() { return keywordLike; }
    public long getOffset() { return offset; }
}
