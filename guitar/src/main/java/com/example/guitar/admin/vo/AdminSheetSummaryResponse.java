package com.example.guitar.admin.vo;

import java.time.LocalDateTime;

public class AdminSheetSummaryResponse {

    private Long id;
    private Long uploaderId;
    private String uploaderNickname;
    private String songName;
    private String singer;
    private String arranger;
    private String sheetType;
    private String difficulty;
    private String keySignature;
    private Integer capoPosition;
    private String tuning;
    private String status;
    private String offlineReason;
    private Long offlineBy;
    private LocalDateTime offlineAt;
    private Long viewCount;
    private Long favoriteCount;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
    private LocalDateTime deletedAt;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public Long getUploaderId() { return uploaderId; }
    public void setUploaderId(Long uploaderId) { this.uploaderId = uploaderId; }
    public String getUploaderNickname() { return uploaderNickname; }
    public void setUploaderNickname(String uploaderNickname) { this.uploaderNickname = uploaderNickname; }
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
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getOfflineReason() { return offlineReason; }
    public void setOfflineReason(String offlineReason) { this.offlineReason = offlineReason; }
    public Long getOfflineBy() { return offlineBy; }
    public void setOfflineBy(Long offlineBy) { this.offlineBy = offlineBy; }
    public LocalDateTime getOfflineAt() { return offlineAt; }
    public void setOfflineAt(LocalDateTime offlineAt) { this.offlineAt = offlineAt; }
    public Long getViewCount() { return viewCount; }
    public void setViewCount(Long viewCount) { this.viewCount = viewCount; }
    public Long getFavoriteCount() { return favoriteCount; }
    public void setFavoriteCount(Long favoriteCount) { this.favoriteCount = favoriteCount; }
    public LocalDateTime getCreateTime() { return createTime; }
    public void setCreateTime(LocalDateTime createTime) { this.createTime = createTime; }
    public LocalDateTime getUpdateTime() { return updateTime; }
    public void setUpdateTime(LocalDateTime updateTime) { this.updateTime = updateTime; }
    public LocalDateTime getDeletedAt() { return deletedAt; }
    public void setDeletedAt(LocalDateTime deletedAt) { this.deletedAt = deletedAt; }
}
