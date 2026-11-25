package com.example.personalagent.service;

import org.junit.jupiter.api.Test;
import org.springframework.http.*;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.server.ResponseStatusException;

import java.nio.charset.StandardCharsets;

import static org.hamcrest.Matchers.containsString;
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;

class DeepSeekFilesTest {
    private final RestTemplate http = new RestTemplate();
    private final MockRestServiceServer server = MockRestServiceServer.bindTo(http).build();
    private final DeepSeekFiles files = new DeepSeekFiles(http);

    @Test
    void uploadsDocumentThenReferencesItsIdAndDeletesIt() {
        upload("rich_layout_recognition", "pdf");
        server.expect(requestTo("https://api.deepseek.com/chat/completions")).andExpect(method(HttpMethod.POST))
            .andExpect(jsonPath("$.model").value("deepseek-flash"))
            .andExpect(jsonPath("$.messages[1].content[0].type").value("file"))
            .andExpect(jsonPath("$.messages[1].content[0].file_id").value("file-api-fixture"))
            .andRespond(withSuccess("{\"choices\":[{\"finish_reason\":\"stop\",\"message\":{\"content\":\"完成\"}}]}", MediaType.APPLICATION_JSON));
        delete();
        assertEquals("完成", files.analyze("original-fixture".getBytes(StandardCharsets.UTF_8), "pdf", "整理", "fixture-key"));
        server.verify();
    }

    @Test
    void expiresAndAttemptsCleanupWhenAnalysisFails() {
        upload("user_data", "jpg");
        server.expect(requestTo("https://api.deepseek.com/chat/completions")).andRespond(withServerError());
        delete();
        ResponseStatusException failure = assertThrows(ResponseStatusException.class,
            () -> files.analyze("original-fixture".getBytes(StandardCharsets.UTF_8), "jpg", "整理", "fixture-key"));
        assertEquals(HttpStatus.BAD_GATEWAY, failure.getStatus());
        server.verify();
    }

    @Test
    void followsSelectedDeepSeekModelFromPicker() {
        upload("user_data", "txt");
        server.expect(requestTo("https://api.deepseek.com/chat/completions")).andExpect(method(HttpMethod.POST))
            .andExpect(jsonPath("$.model").value("deepseek-v4-pro"))
            .andExpect(jsonPath("$.messages[1].content[0].file_id").value("file-api-fixture"))
            .andRespond(withSuccess("{\"choices\":[{\"finish_reason\":\"stop\",\"message\":{\"content\":\"完成\"}}]}", MediaType.APPLICATION_JSON));
        delete();
        assertEquals("完成", files.analyze("original-fixture".getBytes(StandardCharsets.UTF_8), "txt", "整理", "fixture-key", "deepseek-v4-pro"));
        server.verify();
    }

    private void upload(String purpose, String extension) {
        server.expect(requestTo("https://api.deepseek.com/files")).andExpect(method(HttpMethod.POST))
            .andExpect(header(HttpHeaders.AUTHORIZATION,"Bearer fixture-key"))
            .andExpect(content().string(containsString("filename=\"attachment." + extension + "\"")))
            .andExpect(content().string(containsString("\r\n\r\n" + purpose + "\r\n")))
            .andExpect(content().string(containsString("expires_after[seconds]")))
            .andExpect(content().string(containsString("\r\n\r\n3600\r\n")))
            .andExpect(content().string(containsString("original-fixture")))
            .andRespond(withSuccess("{\"id\":\"file-api-fixture\"}", MediaType.APPLICATION_JSON));
    }

    private void delete() {
        server.expect(requestTo("https://api.deepseek.com/files/file-api-fixture")).andExpect(method(HttpMethod.DELETE))
            .andRespond(withSuccess("{\"deleted\":true}", MediaType.APPLICATION_JSON));
    }
}
