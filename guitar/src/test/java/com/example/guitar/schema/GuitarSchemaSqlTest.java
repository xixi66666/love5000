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
        assertThat(schema).contains("create table if not exists guitar_user (");
        assertThat(schema).contains("create table if not exists guitar_sheet (");
        assertThat(schema).contains("create table if not exists guitar_sheet_file (");
        assertThat(schema).contains("create table if not exists guitar_favorite_folder (");
        assertThat(schema).contains("create table if not exists guitar_favorite (");
        assertThat(schema).contains("create table if not exists guitar_admin_action_log (");
        assertThat(schema).contains("create table if not exists guitar_oss_cleanup_task (");
        assertThat(schema).contains("create table if not exists guitar_daily_stat (");
        assertThat(schema).contains("default character set utf8mb4");
        assertThat(schema).contains("uk_guitar_user_phone");
        assertThat(schema).contains("uk_guitar_favorite");
        assertThat(schema).contains("create_time datetime not null default current_timestamp");
        assertThat(schema).contains("update_time datetime not null default current_timestamp on update current_timestamp");
        assertThat(schema).contains("next_retry_at datetime not null default current_timestamp");
        assertThat(schema).contains("key idx_guitar_sheet_uploader (uploader_id, status, create_time)");
        assertThat(schema).contains("key idx_guitar_sheet_filters (status, sheet_type, difficulty, key_signature)");
        assertThat(schema).contains("sort_order int unsigned not null,");
        assertThat(schema).contains("unique key uk_guitar_sheet_file_order (sheet_id, sort_order)");
        assertThat(schema).contains("sort_order int not null default 0,");
        assertThat(schema).contains("key idx_guitar_favorite_folder_user (user_id, sort_order, id)");
        assertThat(schema).contains("ip_address varchar(45)");
        assertThat(schema).contains("key idx_guitar_admin_log_admin (admin_user_id, create_time)");
        assertThat(schema).contains("key idx_guitar_admin_log_target (target_type, target_id, create_time)");
        assertThat(schema).contains("key idx_guitar_admin_log_action (action_type, create_time)");
        assertThat(schema).contains("constraint fk_guitar_admin_log_user");
        assertThat(schema).contains("key idx_guitar_oss_cleanup_poll (status, next_retry_at)");
        assertThat(schema).doesNotMatch("(?s).*\\b(create_time|update_time|next_retry_at)\\s+timestamp\\b.*");
        assertThat(schema).doesNotContain("on delete");
        assertThat(schema).contains("where phone = '<registered-phone>'");
    }
}
