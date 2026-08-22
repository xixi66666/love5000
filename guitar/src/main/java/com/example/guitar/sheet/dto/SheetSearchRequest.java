package com.example.guitar.sheet.dto;

import com.example.guitar.sheet.model.SheetDifficulty;
import com.example.guitar.sheet.model.SheetType;
import com.example.guitar.web.GuitarApiException;
import org.springframework.http.HttpStatus;

import java.util.Locale;

public class SheetSearchRequest {

    private static final int MAX_KEYWORD_LENGTH = 120;
    private static final int MAX_SONG_NAME_LENGTH = 120;
    private static final int MAX_SINGER_LENGTH = 120;
    private static final int MAX_KEY_SIGNATURE_LENGTH = 20;
    private static final int MAX_TUNING_LENGTH = 80;
    private static final long MAX_OFFSET = 5_000_000L;

    public enum Sort {
        LATEST,
        MOST_FAVORITED,
        MOST_VIEWED
    }

    private String keyword;
    private String songName;
    private String singer;
    private String sheetType;
    private String difficulty;
    private String keySignature;
    private Integer capoPosition;
    private String tuning;
    private String sort;
    private Integer page;
    private Integer size;
    private String keywordLike;
    private String songNameLike;
    private String singerLike;
    private long offset;

    public void normalizeAndValidate() {
        keyword = trimToNull(keyword);
        songName = trimToNull(songName);
        singer = trimToNull(singer);
        keySignature = trimToNull(keySignature);
        tuning = trimToNull(tuning);
        sheetType = normalizeEnum(sheetType, SheetType.class);
        difficulty = normalizeEnum(difficulty, SheetDifficulty.class);
        sort = normalizeEnum(sort == null ? Sort.LATEST.name() : sort, Sort.class);
        page = page == null ? 1 : page;
        size = size == null ? 20 : size;
        if (page < 1 || size < 1 || size > 50 || (capoPosition != null && (capoPosition < 0 || capoPosition > 12))
                || exceedsLength(keyword, MAX_KEYWORD_LENGTH) || exceedsLength(songName, MAX_SONG_NAME_LENGTH)
                || exceedsLength(singer, MAX_SINGER_LENGTH) || exceedsLength(keySignature, MAX_KEY_SIGNATURE_LENGTH)
                || exceedsLength(tuning, MAX_TUNING_LENGTH)) {
            throw validationError();
        }
        offset = ((long) page - 1L) * size;
        if (offset > MAX_OFFSET) {
            throw pageTooLargeError();
        }
        keywordLike = toLikePattern(keyword);
        songNameLike = toLikePattern(songName);
        singerLike = toLikePattern(singer);
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

    private boolean exceedsLength(String value, int maximumLength) {
        return value != null && value.length() > maximumLength;
    }

    private GuitarApiException validationError() {
        return new GuitarApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", "请求参数不正确");
    }

    private GuitarApiException pageTooLargeError() {
        return new GuitarApiException(HttpStatus.BAD_REQUEST, "PAGE_TOO_LARGE", "页码超出公开检索范围");
    }

    public String getKeyword() { return keyword; }
    public void setKeyword(String keyword) { this.keyword = keyword; }
    public String getSongName() { return songName; }
    public void setSongName(String songName) { this.songName = songName; }
    public String getSinger() { return singer; }
    public void setSinger(String singer) { this.singer = singer; }
    public String getSheetType() { return sheetType; }
    public void setSheetType(String sheetType) { this.sheetType = sheetType; }
    public String getDifficulty() { return difficulty; }
    public void setDifficulty(String difficulty) { this.difficulty = difficulty; }
    public String getKeySignature() { return keySignature; }
    public void setKeySignature(String keySignature) { this.keySignature = keySignature; }
    public Integer getCapoPosition() { return capoPosition; }
    public void setCapoPosition(Integer capoPosition) { this.capoPosition = capoPosition; }
    public String getTuning() { return tuning; }
    public void setTuning(String tuning) { this.tuning = tuning; }
    public String getSort() { return sort; }
    public void setSort(String sort) { this.sort = sort; }
    public Integer getPage() { return page; }
    public void setPage(Integer page) { this.page = page; }
    public Integer getSize() { return size; }
    public void setSize(Integer size) { this.size = size; }
    public String getKeywordLike() { return keywordLike; }
    public String getSongNameLike() { return songNameLike; }
    public String getSingerLike() { return singerLike; }
    public long getOffset() { return offset; }
}
