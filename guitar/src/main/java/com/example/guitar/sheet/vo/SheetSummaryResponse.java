package com.example.guitar.sheet.vo;

import java.time.LocalDateTime;

public class SheetSummaryResponse {

    private Long id;
    private String songName;
    private String singer;
    private String arranger;
    private String sheetType;
    private String difficulty;
    private String keySignature;
    private Integer capoPosition;
    private String tuning;
    private String uploaderNickname;
    private Long viewCount;
    private Long favoriteCount;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getSongName() { return songName; }
    public void setSongName(String songName) { this.songName = songName; }
    public String getSinger() { return singer; }
    public void setSinger(String singer) { this.singer = singer; }
    public String getArranger() { return arranger; }
    public void setArranger(String arranger) { this.arranger = arranger; }
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
    public String getUploaderNickname() { return uploaderNickname; }
    public void setUploaderNickname(String uploaderNickname) { this.uploaderNickname = uploaderNickname; }
    public Long getViewCount() { return viewCount; }
    public void setViewCount(Long viewCount) { this.viewCount = viewCount; }
    public Long getFavoriteCount() { return favoriteCount; }
    public void setFavoriteCount(Long favoriteCount) { this.favoriteCount = favoriteCount; }
    public LocalDateTime getCreateTime() { return createTime; }
    public void setCreateTime(LocalDateTime createTime) { this.createTime = createTime; }
    public LocalDateTime getUpdateTime() { return updateTime; }
    public void setUpdateTime(LocalDateTime updateTime) { this.updateTime = updateTime; }
}
