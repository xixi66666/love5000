package com.example.guitar.sheet.vo;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

public class SheetDetailResponse extends SheetSummaryResponse {

    private String description;
    private List<FileResponse> files = new ArrayList<FileResponse>();

    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }
    public List<FileResponse> getFiles() { return files; }
    public void setFiles(List<FileResponse> files) { this.files = files; }

    public static class FileResponse {
        private Long id;
        private String originalFilename;
        private String mimeType;
        private String fileExtension;
        private Long fileSize;
        private Integer sortOrder;
        private String url;
        private LocalDateTime createTime;

        public Long getId() { return id; }
        public void setId(Long id) { this.id = id; }
        public String getOriginalFilename() { return originalFilename; }
        public void setOriginalFilename(String originalFilename) { this.originalFilename = originalFilename; }
        public String getMimeType() { return mimeType; }
        public void setMimeType(String mimeType) { this.mimeType = mimeType; }
        public String getFileExtension() { return fileExtension; }
        public void setFileExtension(String fileExtension) { this.fileExtension = fileExtension; }
        public Long getFileSize() { return fileSize; }
        public void setFileSize(Long fileSize) { this.fileSize = fileSize; }
        public Integer getSortOrder() { return sortOrder; }
        public void setSortOrder(Integer sortOrder) { this.sortOrder = sortOrder; }
        public String getUrl() { return url; }
        public void setUrl(String url) { this.url = url; }
        public LocalDateTime getCreateTime() { return createTime; }
        public void setCreateTime(LocalDateTime createTime) { this.createTime = createTime; }
    }
}
