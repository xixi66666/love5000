package com.example.guitar.sheet.dto;

import com.example.guitar.sheet.model.FileMode;
import com.example.guitar.sheet.model.SheetDifficulty;
import com.example.guitar.sheet.model.SheetType;

public class SheetSaveRequest {

    private String songName;
    private String singer;
    private String arranger;
    private String description;
    private String keywords;
    private SheetType sheetType;
    private SheetDifficulty difficulty;
    private String keySignature;
    private Integer capoPosition;
    private String tuning;
    private FileMode fileMode;

    public String getSongName() { return songName; }
    public void setSongName(String songName) { this.songName = songName; }
    public String getSinger() { return singer; }
    public void setSinger(String singer) { this.singer = singer; }
    public String getArranger() { return arranger; }
    public void setArranger(String arranger) { this.arranger = arranger; }
    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }
    public String getKeywords() { return keywords; }
    public void setKeywords(String keywords) { this.keywords = keywords; }
    public SheetType getSheetType() { return sheetType; }
    public void setSheetType(SheetType sheetType) { this.sheetType = sheetType; }
    public SheetDifficulty getDifficulty() { return difficulty; }
    public void setDifficulty(SheetDifficulty difficulty) { this.difficulty = difficulty; }
    public String getKeySignature() { return keySignature; }
    public void setKeySignature(String keySignature) { this.keySignature = keySignature; }
    public Integer getCapoPosition() { return capoPosition; }
    public void setCapoPosition(Integer capoPosition) { this.capoPosition = capoPosition; }
    public String getTuning() { return tuning; }
    public void setTuning(String tuning) { this.tuning = tuning; }
    public FileMode getFileMode() { return fileMode; }
    public void setFileMode(FileMode fileMode) { this.fileMode = fileMode; }
}
