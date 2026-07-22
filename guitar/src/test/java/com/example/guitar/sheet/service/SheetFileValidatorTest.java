package com.example.guitar.sheet.service;

import com.example.guitar.sheet.model.FileMode;
import com.example.guitar.sheet.dto.SheetSaveRequest;
import com.example.guitar.sheet.model.SheetDifficulty;
import com.example.guitar.sheet.model.SheetType;
import com.example.guitar.web.GuitarApiException;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockMultipartFile;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class SheetFileValidatorTest {

    private final SheetFileValidator validator = new SheetFileValidator();

    @Test
    void acceptsPdfAndDerivesSafeMetadataWithoutTrustingClientContentType() {
        MockMultipartFile pdf = file("files", "../score.PDF", "image/png", bytes("%PDF-1.7"));

        List<SheetFileValidator.ValidatedSheetFile> files = validator.validateFiles(FileMode.PDF,
                Collections.singletonList(pdf));

        assertThat(files).singleElement().satisfies(validated -> {
            assertThat(validated.getOriginalFilename()).isEqualTo("score.PDF");
            assertThat(validated.getFileExtension()).isEqualTo("pdf");
            assertThat(validated.getMimeType()).isEqualTo("application/pdf");
        });
    }

    @Test
    void acceptsOrderedImagesWithOnlySupportedExtensionAndMatchingMagic() {
        List<SheetFileValidator.ValidatedSheetFile> files = validator.validateFiles(FileMode.IMAGES, Arrays.asList(
                file("files", "one.jpg", "application/octet-stream", new byte[]{(byte) 0xFF, (byte) 0xD8, (byte) 0xFF}),
                file("files", "two.png", "image/jpeg", pngHeader()),
                file("files", "three.webp", "image/png", webpHeader())));

        assertThat(files).extracting(SheetFileValidator.ValidatedSheetFile::getMimeType)
                .containsExactly("image/jpeg", "image/png", "image/webp");
        assertThat(files).extracting(SheetFileValidator.ValidatedSheetFile::getSortOrder)
                .containsExactly(1, 2, 3);
    }

    @Test
    void rejectsWrongCountSizeMixedAndFakeContentBeforeUpload() {
        assertInvalid(FileMode.PDF, Arrays.asList(
                file("files", "one.pdf", null, bytes("%PDF")),
                file("files", "two.pdf", null, bytes("%PDF"))));
        assertInvalid(FileMode.IMAGES, Collections.<MockMultipartFile>emptyList());
        assertInvalid(FileMode.IMAGES, Collections.singletonList(file("files", "fake.png", null, bytes("<svg"))));
        assertInvalid(FileMode.IMAGES, Collections.singletonList(file("files", "photo.gif", null, bytes("GIF89a"))));
        assertInvalid(FileMode.PDF, Collections.singletonList(file("files", "fake.pdf", null, bytes("not-a-pdf"))));
        assertInvalid(FileMode.IMAGES, Collections.singletonList(file("files", "large.jpg", null,
                new byte[10 * 1024 * 1024 + 1])));
        assertInvalid(FileMode.PDF, Collections.singletonList(file("files", "large.pdf", null,
                new byte[30 * 1024 * 1024 + 1])));
        assertInvalid(FileMode.PDF, Collections.singletonList(file("files", repeat('a', 252) + ".pdf", null,
                bytes("%PDF"))));
    }

    @Test
    void normalizesBoundedMetadataAndRejectsMissingOrOutOfRangeValues() {
        SheetSaveRequest valid = metadata();
        valid.setSongName(" Song ");
        valid.setArranger(" ");
        validator.normalizeAndValidateMetadata(valid);
        assertThat(valid.getSongName()).isEqualTo("Song");
        assertThat(valid.getArranger()).isNull();

        SheetSaveRequest missingSinger = metadata();
        missingSinger.setSinger(" ");
        assertMetadataInvalid(missingSinger);
        SheetSaveRequest longDescription = metadata();
        longDescription.setDescription(repeat('d', 1001));
        assertMetadataInvalid(longDescription);
        SheetSaveRequest invalidCapo = metadata();
        invalidCapo.setCapoPosition(13);
        assertMetadataInvalid(invalidCapo);
        SheetSaveRequest missingType = metadata();
        missingType.setSheetType(null);
        assertMetadataInvalid(missingType);
        SheetSaveRequest missingMode = metadata();
        missingMode.setFileMode(null);
        assertMetadataInvalid(missingMode);
    }

    private void assertInvalid(FileMode mode, List<? extends org.springframework.web.multipart.MultipartFile> files) {
        assertThatThrownBy(() -> validator.validateFiles(mode, files))
                .isInstanceOfSatisfying(GuitarApiException.class,
                        exception -> assertThat(exception.getCode()).isEqualTo("SHEET_FILE_INVALID"));
    }

    private MockMultipartFile file(String name, String filename, String contentType, byte[] content) {
        return new MockMultipartFile(name, filename, contentType, content);
    }

    private SheetSaveRequest metadata() {
        SheetSaveRequest request = new SheetSaveRequest();
        request.setSongName("Song");
        request.setSinger("Singer");
        request.setSheetType(SheetType.TAB);
        request.setDifficulty(SheetDifficulty.BEGINNER);
        request.setKeySignature("C");
        request.setCapoPosition(0);
        request.setTuning("Standard");
        request.setFileMode(FileMode.PDF);
        return request;
    }

    private void assertMetadataInvalid(SheetSaveRequest request) {
        assertThatThrownBy(() -> validator.normalizeAndValidateMetadata(request))
                .isInstanceOfSatisfying(GuitarApiException.class,
                        exception -> assertThat(exception.getCode()).isEqualTo("SHEET_METADATA_INVALID"));
    }

    private String repeat(char value, int count) {
        StringBuilder builder = new StringBuilder(count);
        for (int index = 0; index < count; index++) {
            builder.append(value);
        }
        return builder.toString();
    }

    private byte[] pngHeader() {
        return new byte[]{(byte) 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A};
    }

    private byte[] webpHeader() {
        return new byte[]{'R', 'I', 'F', 'F', 0, 0, 0, 0, 'W', 'E', 'B', 'P'};
    }

    private byte[] bytes(String value) {
        return value.getBytes(java.nio.charset.StandardCharsets.US_ASCII);
    }
}
