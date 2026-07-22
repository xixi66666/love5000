package com.example.guitar.storage.dao;

import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;

import static org.assertj.core.api.Assertions.assertThat;

class OssCleanupTaskMapperContractTest {
    @Test
    void cleanupMapperUsesBoundExpectedStateClaiming() throws IOException {
        InputStream stream = getClass().getClassLoader().getResourceAsStream("mapper/storage/OssCleanupTaskMapper.xml");
        assertThat(stream).isNotNull();
        String xml;
        try (InputStream input = stream) {
            byte[] data = new byte[8192]; int length = input.read(data);
            xml = new String(data, 0, length, StandardCharsets.UTF_8);
        }
        assertThat(xml).contains("<select id=\"findDuePending\"");
        assertThat(xml).contains("LIMIT #{limit}");
        assertThat(xml).contains("<update id=\"claimPending\"");
        assertThat(xml).contains("status='PENDING' AND next_retry_at &lt;= #{now}");
        assertThat(xml).contains("<update id=\"recoverStaleProcessing\"");
        assertThat(xml).doesNotContain("${");
    }
}
