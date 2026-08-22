package com.example.guitar.favorite.dao;

import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;

import static org.assertj.core.api.Assertions.assertThat;

class FavoriteMapperContractTest {

    private static final String MAPPER_RESOURCE = "mapper/favorite/FavoriteMapper.xml";

    @Test
    void mapperScopesEveryFolderOperationToOwnerAndKeepsFavoriteCountersSafe() throws IOException {
        String xml = readMapperXml();

        assertThat(xml).contains("<mapper namespace=\"com.example.guitar.favorite.dao.FavoriteDao\">");
        assertThat(xml).doesNotContain("${");
        assertThat(xml).contains("user_id = #{userId}");
        assertThat(xml).contains("status = 'PUBLISHED'");
        assertThat(xml).contains("deleted_at IS NULL");
        assertThat(xml).contains("CASE WHEN favorite_count > 0 THEN favorite_count - 1 ELSE 0 END");
        assertThat(xml).contains("<foreach collection=\"sheetIds\"");
        assertThat(xml).contains("ORDER BY f.sort_order ASC, f.id ASC");
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
