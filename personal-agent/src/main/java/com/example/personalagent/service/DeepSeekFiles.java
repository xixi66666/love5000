package com.example.personalagent.service;

import com.example.common.ai.ModelProperties;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.*;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.server.ResponseStatusException;

import java.util.Arrays;
import java.net.HttpURLConnection;
import java.io.IOException;

import static com.example.personalagent.Api.*;

@Service
public class DeepSeekFiles {
    private static final String BASE = "https://api.deepseek.com";
    static final String FILE_MODEL = "deepseek-flash";
    private final RestTemplate http;

    @Autowired
    public DeepSeekFiles() {
        SimpleClientHttpRequestFactory requests = new SimpleClientHttpRequestFactory() {
            @Override protected void prepareConnection(HttpURLConnection connection, String method) throws IOException {
                super.prepareConnection(connection, method);
                connection.setInstanceFollowRedirects(false);
            }
        };
        requests.setConnectTimeout(10000);
        requests.setReadTimeout(180000);
        http = new RestTemplate(requests);
    }

    DeepSeekFiles(RestTemplate http) {
        this.http = http;
    }

    public String analyze(byte[] bytes, String extension, String instruction) {
        return analyzeWithModel(bytes, extension, instruction, "");
    }

    /** model 为空时使用默认 deepseek-flash；传入统一模型选择里的 DeepSeek 型号即可跟随顶部栏选择器。 */
    public String analyzeWithModel(byte[] bytes, String extension, String instruction, String model) {
        ModelProperties.Provider provider = ModelProperties.load().provider("deepseek");
        if (provider == null || provider.apiKey().isEmpty()) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,
                "请在根目录 model.properties 配置 DeepSeek 官方 API 密钥");
        }
        return analyze(bytes, extension, instruction, provider.apiKey(), model);
    }

    String analyze(byte[] bytes, String extension, String instruction, String apiKey) {
        return analyze(bytes, extension, instruction, apiKey, "");
    }

    String analyze(byte[] bytes, String extension, String instruction, String apiKey, String model) {
        String selected = model == null || model.trim().isEmpty() ? FILE_MODEL : model.trim();
        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(apiKey);
        HttpHeaders uploadHeaders = new HttpHeaders();
        uploadHeaders.putAll(headers);
        uploadHeaders.setContentType(MediaType.MULTIPART_FORM_DATA);
        LinkedMultiValueMap<String,Object> fields = new LinkedMultiValueMap<>();
        fields.add("purpose", extension.matches("pdf|docx?|pptx?") ? "rich_layout_recognition" : "user_data");
        fields.add("expires_after[anchor]", "created_at");
        fields.add("expires_after[seconds]", "3600");
        fields.add("file", new ByteArrayResource(bytes) {
            @Override public String getFilename() { return "attachment." + extension; }
        });

        String fileId = "";
        try {
            JsonNode uploaded = http.postForObject(BASE + "/files", new HttpEntity<>(fields, uploadHeaders), JsonNode.class);
            if (uploaded == null || !uploaded.path("id").asText().matches("file-api-[A-Za-z0-9_-]{1,128}")) {
                throw new RestClientException("Missing file ID");
            }
            fileId = uploaded.path("id").asText();
            JsonNode result = http.postForObject(BASE + "/chat/completions", new HttpEntity<>(map(
                "model",selected,"max_tokens",6000,"thinking",map("type","disabled"),
                "messages",Arrays.asList(map("role","system","content",instruction),map("role","user","content",Arrays.asList(
                    map("type","file","file_id",fileId),map("type","text","text","请按要求整理本次上传的附件。"))))
            ), headers), JsonNode.class);
            JsonNode choice = result == null ? null : result.path("choices").path(0);
            String answer = choice == null ? "" : choice.path("message").path("content").asText().trim();
            if (choice == null || !"stop".equals(choice.path("finish_reason").asText()) || answer.isEmpty() || answer.length() > 60000) {
                throw new RestClientException("Incomplete file analysis");
            }
            return answer;
        } catch (RestClientException failure) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "DeepSeek 文件处理失败，请检查官方密钥、余额和文件格式后重试");
        } finally {
            if (!fileId.isEmpty()) {
                try { http.exchange(BASE + "/files/{id}", HttpMethod.DELETE, new HttpEntity<>(headers), Void.class, fileId); }
                catch (RestClientException unavailable) {}
            }
        }
    }
}
