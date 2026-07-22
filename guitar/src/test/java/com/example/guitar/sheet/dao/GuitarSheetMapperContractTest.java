package com.example.guitar.sheet.dao;

import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;

import static org.assertj.core.api.Assertions.assertThat;

class GuitarSheetMapperContractTest {

    private static final String MAPPER_RESOURCE = "mapper/sheet/GuitarSheetMapper.xml";

    @Test
    void publicSheetMapperKeepsTheRequiredQuerySafetyAndVisibilityContracts() throws IOException {
        String mapperXml = readMapperXml();

        assertThat(mapperXml).contains("<mapper namespace=\"com.example.guitar.sheet.dao.GuitarSheetDao\">");
        assertThat(mapperXml).doesNotContain("${");
        assertThat(mapperXml).contains("<choose>");
        assertThat(mapperXml).contains("request.sort == 'MOST_FAVORITED'");
        assertThat(mapperXml).contains("request.sort == 'MOST_VIEWED'");
        assertThat(mapperXml).contains("ESCAPE '\\\\'");
        assertThat(mapperXml).contains("s.status = 'PUBLISHED' AND s.deleted_at IS NULL");
        assertThat(mapperXml).contains("ON DUPLICATE KEY UPDATE sheet_view_count = sheet_view_count + 1");
    }

    @Test
    void latestPublicSheetOrderingDoesNotIncludeAConstantStatusColumn() throws IOException {
        String mapperXml = readMapperXml();

        assertThat(mapperXml).contains("<otherwise>s.create_time DESC, s.id DESC</otherwise>");
        assertThat(mapperXml).doesNotContain("s.status ASC, s.create_time DESC");
    }

    @Test
    void ownerMutationMapperKeepsSoftDeleteAndBoundParameters() throws IOException {
        String mapperXml = readMapperXml();

        assertThat(mapperXml).contains("<select id=\"findActiveByIdForOwnerForUpdate\"");
        assertThat(mapperXml).contains("FOR UPDATE");
        assertThat(mapperXml).contains("<update id=\"updateMetadata\"");
        assertThat(mapperXml).contains("<update id=\"updateMetadataAndFileMode\"");
        assertThat(mapperXml).contains("<update id=\"markDeleted\"");
        assertThat(mapperXml).contains("DELETE FROM guitar_favorite WHERE sheet_id=#{sheetId}");
        assertThat(mapperXml).doesNotContain("${");
    }

    private String readMapperXml() throws IOException {
        InputStream stream = getClass().getClassLoader().getResourceAsStream(MAPPER_RESOURCE);
        assertThat(stream).as("mapper resource %s", MAPPER_RESOURCE).isNotNull();
        try (InputStream input = stream) {
            byte[] bytes = new byte[8192];
            StringBuilder xml = new StringBuilder();
            int length;
            while ((length = input.read(bytes)) != -1) {
                xml.append(new String(bytes, 0, length, StandardCharsets.UTF_8));
            }
            return xml.toString();
        }
    }
}
