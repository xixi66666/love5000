package com.example.guitar.schema;

import org.junit.jupiter.api.Test;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.Locale;

import static org.assertj.core.api.Assertions.assertThat;

class GuitarSchemaSqlTest {

    @Test
    void schemaDefinesRequiredGuitarPlatformTablesAndSafetyPlaceholder() throws IOException {
        String schema = loadSchema();

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
        assertThat(schema).contains("claim_version bigint unsigned not null default 0");
        assertThat(schema).contains("processing_started_at datetime default null");
        assertThat(schema).contains("key idx_guitar_sheet_uploader (uploader_id, status, create_time)");
        assertThat(schema).contains("key idx_guitar_sheet_filters (status, sheet_type, difficulty, key_signature)");
        assertThat(schema).contains("key idx_guitar_sheet_public (status, create_time, id)");
        assertThat(schema).contains("sort_order int unsigned not null,");
        assertThat(schema).contains("unique key uk_guitar_sheet_file_order (sheet_id, sort_order)");
        assertThat(schema).doesNotContain("key idx_guitar_sheet_file_sheet (sheet_id)");
        assertThat(schema).contains("sort_order int not null default 0,");
        assertThat(schema).contains("key idx_guitar_favorite_folder_user (user_id, sort_order, id)");
        assertThat(schema).contains("unique key uk_guitar_favorite_folder_owner (id, user_id)");
        assertThat(schema).contains("constraint fk_guitar_favorite_folder_owner foreign key (folder_id, user_id) references guitar_favorite_folder (id, user_id)");
        assertThat(schema).doesNotContain("constraint fk_guitar_favorite_folder foreign key (folder_id)");
        assertThat(schema).contains("ip_address varchar(45)");
        assertThat(schema).contains("key idx_guitar_admin_log_admin (admin_user_id, create_time)");
        assertThat(schema).contains("key idx_guitar_admin_log_target (target_type, target_id, create_time)");
        assertThat(schema).contains("key idx_guitar_admin_log_action (action_type, create_time)");
        assertThat(schema).contains("constraint fk_guitar_admin_log_user");
        assertThat(schema).contains("key idx_guitar_oss_cleanup_poll (status, next_retry_at)");
        assertThat(schema).contains("key idx_guitar_oss_cleanup_object (object_key(191))");
        assertThat(schema).doesNotMatch("(?s).*\\b(create_time|update_time|next_retry_at)\\s+timestamp\\b.*");
        assertThat(schema).doesNotContain("on delete");
        assertThat(schema).contains("where phone = '<registered-phone>'");
    }

    @Test
    void schemaLoadedFromClasspathHasBalancedDelimitersAndDependencyOrder() throws IOException {
        String schema = loadSchema();
        String[] tableDefinitions = {
                "create table if not exists guitar_user (",
                "create table if not exists guitar_sheet (",
                "create table if not exists guitar_sheet_file (",
                "create table if not exists guitar_favorite_folder (",
                "create table if not exists guitar_favorite (",
                "create table if not exists guitar_admin_action_log (",
                "create table if not exists guitar_oss_cleanup_task (",
                "create table if not exists guitar_daily_stat ("
        };

        int previousPosition = -1;
        for (String tableDefinition : tableDefinitions) {
            int position = schema.indexOf(tableDefinition);
            assertThat(position).as(tableDefinition).isGreaterThan(previousPosition);
            previousPosition = position;
        }

        assertThat(countOccurrences(schema, "create table if not exists guitar_")).isEqualTo(8);
        assertThat(hasBalancedParentheses(schema)).isTrue();
        assertThat(schema).contains(
                "constraint fk_guitar_user_banned_by foreign key (banned_by) references guitar_user (id)",
                "constraint fk_guitar_sheet_uploader foreign key (uploader_id) references guitar_user (id)",
                "constraint fk_guitar_sheet_offline_by foreign key (offline_by) references guitar_user (id)",
                "constraint fk_guitar_sheet_file_sheet foreign key (sheet_id) references guitar_sheet (id)",
                "constraint fk_guitar_favorite_user foreign key (user_id) references guitar_user (id)",
                "constraint fk_guitar_favorite_sheet foreign key (sheet_id) references guitar_sheet (id)",
                "constraint fk_guitar_admin_log_user foreign key (admin_user_id) references guitar_user (id)");
    }

    private String loadSchema() throws IOException {
        InputStream inputStream = getClass().getClassLoader().getResourceAsStream("db/guitar-schema.sql");
        assertThat(inputStream).as("classpath schema resource").isNotNull();

        try (InputStream schemaInput = inputStream; ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[1024];
            int bytesRead;
            while ((bytesRead = schemaInput.read(buffer)) != -1) {
                output.write(buffer, 0, bytesRead);
            }
            return new String(output.toByteArray(), StandardCharsets.UTF_8).toLowerCase(Locale.ROOT);
        }
    }

    private int countOccurrences(String content, String token) {
        int count = 0;
        int position = 0;
        while ((position = content.indexOf(token, position)) >= 0) {
            count++;
            position += token.length();
        }
        return count;
    }

    private boolean hasBalancedParentheses(String content) {
        int depth = 0;
        boolean inSingleQuotedText = false;
        for (int index = 0; index < content.length(); index++) {
            char character = content.charAt(index);
            if (character == '\'') {
                inSingleQuotedText = !inSingleQuotedText;
            } else if (!inSingleQuotedText && character == '(') {
                depth++;
            } else if (!inSingleQuotedText && character == ')') {
                depth--;
                if (depth < 0) {
                    return false;
                }
            }
        }
        return !inSingleQuotedText && depth == 0;
    }
}
