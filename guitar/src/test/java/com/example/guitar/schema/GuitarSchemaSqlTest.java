package com.example.guitar.schema;

import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Locale;

import static org.assertj.core.api.Assertions.assertThat;

class GuitarSchemaSqlTest {

    @Test
    void schemaDefinesRequiredGuitarPlatformTablesAndSafetyPlaceholder() throws IOException {
        Path schemaPath = Paths.get("src", "main", "resources", "db", "guitar-schema.sql");
        assertThat(Files.exists(schemaPath)).isTrue();

        String schema = new String(Files.readAllBytes(schemaPath), StandardCharsets.UTF_8)
                .toLowerCase(Locale.ROOT);

        assertThat(schema).contains("create database if not exists guitar");
        assertThat(schema).contains("guitar_user");
        assertThat(schema).contains("guitar_sheet");
        assertThat(schema).contains("guitar_sheet_file");
        assertThat(schema).contains("guitar_favorite_folder");
        assertThat(schema).contains("guitar_favorite");
        assertThat(schema).contains("guitar_admin_action_log");
        assertThat(schema).contains("guitar_oss_cleanup_task");
        assertThat(schema).contains("guitar_daily_stat");
        assertThat(schema).contains("default character set utf8mb4");
        assertThat(schema).contains("uk_guitar_user_phone");
        assertThat(schema).contains("uk_guitar_favorite");
        assertThat(schema).contains("where phone = '<registered-phone>'");
    }
}
