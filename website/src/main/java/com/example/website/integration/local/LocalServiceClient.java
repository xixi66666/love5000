package com.example.website.integration.local;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

@Component
public class LocalServiceClient {
    private final ObjectMapper mapper;

    public LocalServiceClient(ObjectMapper mapper) {
        this.mapper = mapper;
    }

    public JsonNode get(int port, String path) {
        try {
            return exchange(port, path, null, 4000);
        } catch (LocalServiceException exception) {
            return null;
        }
    }

    public JsonNode post(int port, String path, String body, int timeoutMs) {
        return exchange(port, path, body, timeoutMs);
    }

    private JsonNode exchange(int port, String path, String body, int timeoutMs) {
        if (port < 1 || port > 65535 || !path.startsWith("/")) {
            throw new LocalServiceException(503, "本机服务配置无效");
        }
        HttpURLConnection connection = null;
        try {
            connection = (HttpURLConnection) new URL("http://127.0.0.1:" + port + path).openConnection();
            connection.setConnectTimeout(2000);
            connection.setReadTimeout(timeoutMs);
            connection.setInstanceFollowRedirects(false);
            connection.setUseCaches(false);
            if (body != null) {
                connection.setRequestMethod("POST");
                connection.setRequestProperty("Content-Type", "application/json");
                connection.setRequestProperty("X-AIMedia-Client", "studio");
                connection.setDoOutput(true);
                try (java.io.OutputStream output = connection.getOutputStream()) {
                    output.write(body.getBytes(StandardCharsets.UTF_8));
                }
            }
            int status = connection.getResponseCode();
            if (status < 200 || status >= 300) {
                throw new LocalServiceException(status == 409 ? 409 : 503,
                        status == 409 ? "服务正在处理请求，请完成或停止当前任务后重试" : "本机服务操作失败，请检查该服务日志");
            }
            try (InputStream input = connection.getInputStream()) {
                JsonNode value = mapper.readTree(input);
                if (value == null) throw new IOException("Empty response");
                return value;
            }
        } catch (IOException exception) {
            throw new LocalServiceException(503, "本机服务未就绪或操作超时，请检查服务状态和日志");
        } finally {
            if (connection != null) connection.disconnect();
        }
    }
}
