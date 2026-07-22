package com.example.guitar.sheet.service;

import com.example.guitar.sheet.model.FileMode;
import com.example.guitar.sheet.dto.SheetSaveRequest;
import com.example.guitar.web.GuitarApiException;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;

@Component
public class SheetFileValidator {

    private static final long MAX_PDF_SIZE = 30L * 1024L * 1024L;
    private static final long MAX_IMAGE_SIZE = 10L * 1024L * 1024L;
    private static final int MAX_IMAGE_COUNT = 20;

    public void normalizeAndValidateMetadata(SheetSaveRequest request) {
        if (request == null) {
            throw invalidMetadata();
        }
        request.setSongName(required(request.getSongName(), 120));
        request.setSinger(required(request.getSinger(), 120));
        request.setArranger(optional(request.getArranger(), 120));
        request.setDescription(optional(request.getDescription(), 1000));
        request.setKeywords(optional(request.getKeywords(), 500));
        request.setKeySignature(required(request.getKeySignature(), 20));
        request.setTuning(required(request.getTuning(), 80));
        if (request.getSheetType() == null || request.getDifficulty() == null
                || request.getCapoPosition() != null
                && (request.getCapoPosition() < 0 || request.getCapoPosition() > 12)) {
            throw invalidMetadata();
        }
        requireFileMode(request.getFileMode());
    }

    public FileMode requireFileMode(FileMode fileMode) {
        if (fileMode == null) {
            throw invalidMetadata();
        }
        return fileMode;
    }

    public void validateFileModeBoundary(FileMode fileMode, int fileCount) {
        requireFileMode(fileMode);
        if (fileCount < 0 || (fileMode == FileMode.PDF && fileCount != 1)
                || (fileMode == FileMode.IMAGES && (fileCount < 1 || fileCount > MAX_IMAGE_COUNT))) {
            throw invalidMetadata();
        }
    }

    public List<ValidatedSheetFile> validateFiles(FileMode fileMode,
                                                    List<? extends MultipartFile> multipartFiles) {
        List<? extends MultipartFile> files = multipartFiles == null
                ? Collections.<MultipartFile>emptyList() : multipartFiles;
        requireFileMode(fileMode);
        if ((fileMode == FileMode.PDF && files.size() != 1)
                || (fileMode == FileMode.IMAGES && (files.isEmpty() || files.size() > MAX_IMAGE_COUNT))) {
            throw invalidFile();
        }
        List<ValidatedSheetFile> validatedFiles = new ArrayList<ValidatedSheetFile>();
        for (int index = 0; index < files.size(); index++) {
            MultipartFile file = files.get(index);
            validatedFiles.add(validateFile(fileMode, file, index + 1));
        }
        return validatedFiles;
    }

    private ValidatedSheetFile validateFile(FileMode fileMode, MultipartFile file, int sortOrder) {
        if (file == null || file.isEmpty()) {
            throw invalidFile();
        }
        String originalFilename = sanitizeOriginalFilename(file.getOriginalFilename());
        String extension = extensionOf(originalFilename);
        long maximumSize = fileMode == FileMode.PDF ? MAX_PDF_SIZE : MAX_IMAGE_SIZE;
        if (file.getSize() > maximumSize || !hasAllowedExtension(fileMode, extension)
                || !hasExpectedMagic(file, extension)) {
            throw invalidFile();
        }
        return new ValidatedSheetFile(file, originalFilename, extension, mimeTypeFor(extension), file.getSize(), sortOrder);
    }

    private boolean hasAllowedExtension(FileMode fileMode, String extension) {
        if (fileMode == FileMode.PDF) {
            return "pdf".equals(extension);
        }
        return "jpg".equals(extension) || "jpeg".equals(extension)
                || "png".equals(extension) || "webp".equals(extension);
    }

    private boolean hasExpectedMagic(MultipartFile file, String extension) {
        byte[] header = new byte[12];
        try (InputStream input = file.getInputStream()) {
            int read = 0;
            while (read < header.length) {
                int count = input.read(header, read, header.length - read);
                if (count < 0) {
                    break;
                }
                read += count;
            }
            if ("pdf".equals(extension)) {
                return read >= 4 && header[0] == '%' && header[1] == 'P' && header[2] == 'D' && header[3] == 'F';
            }
            if ("jpg".equals(extension) || "jpeg".equals(extension)) {
                return read >= 3 && (header[0] & 0xFF) == 0xFF
                        && (header[1] & 0xFF) == 0xD8 && (header[2] & 0xFF) == 0xFF;
            }
            if ("png".equals(extension)) {
                return read >= 8 && (header[0] & 0xFF) == 0x89 && header[1] == 0x50
                        && header[2] == 0x4E && header[3] == 0x47 && header[4] == 0x0D
                        && header[5] == 0x0A && header[6] == 0x1A && header[7] == 0x0A;
            }
            return read >= 12 && header[0] == 'R' && header[1] == 'I' && header[2] == 'F'
                    && header[3] == 'F' && header[8] == 'W' && header[9] == 'E'
                    && header[10] == 'B' && header[11] == 'P';
        } catch (IOException exception) {
            return false;
        }
    }

    private String required(String value, int maximumLength) {
        String normalized = optional(value, maximumLength);
        if (normalized == null) {
            throw invalidMetadata();
        }
        return normalized;
    }

    private String optional(String value, int maximumLength) {
        if (value == null) {
            return null;
        }
        String normalized = value.trim();
        if (normalized.isEmpty()) {
            return null;
        }
        if (normalized.length() > maximumLength) {
            throw invalidMetadata();
        }
        return normalized;
    }

    private String sanitizeOriginalFilename(String originalFilename) {
        if (originalFilename == null) {
            return "";
        }
        String normalized = originalFilename.replace('\\', '/');
        int slash = normalized.lastIndexOf('/');
        String basename = slash >= 0 ? normalized.substring(slash + 1) : normalized;
        return basename.replaceAll("[\\p{Cntrl}]", "").trim();
    }

    private String extensionOf(String filename) {
        int dot = filename.lastIndexOf('.');
        return dot < 0 || dot == filename.length() - 1 ? ""
                : filename.substring(dot + 1).toLowerCase(Locale.ROOT);
    }

    private String mimeTypeFor(String extension) {
        if ("pdf".equals(extension)) {
            return "application/pdf";
        }
        if ("png".equals(extension)) {
            return "image/png";
        }
        if ("webp".equals(extension)) {
            return "image/webp";
        }
        return "image/jpeg";
    }

    private GuitarApiException invalidMetadata() {
        return new GuitarApiException(HttpStatus.BAD_REQUEST, "SHEET_METADATA_INVALID", "曲谱元数据不正确");
    }

    private GuitarApiException invalidFile() {
        return new GuitarApiException(HttpStatus.BAD_REQUEST, "SHEET_FILE_INVALID", "曲谱文件格式不正确");
    }

    public static final class ValidatedSheetFile {
        private final MultipartFile multipartFile;
        private final String originalFilename;
        private final String fileExtension;
        private final String mimeType;
        private final long fileSize;
        private final int sortOrder;

        ValidatedSheetFile(MultipartFile multipartFile, String originalFilename, String fileExtension,
                           String mimeType, long fileSize, int sortOrder) {
            this.multipartFile = multipartFile;
            this.originalFilename = originalFilename;
            this.fileExtension = fileExtension;
            this.mimeType = mimeType;
            this.fileSize = fileSize;
            this.sortOrder = sortOrder;
        }

        public MultipartFile getMultipartFile() { return multipartFile; }
        public String getOriginalFilename() { return originalFilename; }
        public String getFileExtension() { return fileExtension; }
        public String getMimeType() { return mimeType; }
        public long getFileSize() { return fileSize; }
        public int getSortOrder() { return sortOrder; }
    }
}
