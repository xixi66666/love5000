package com.example.website.integration.models;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.*;
import java.net.*;

/** 固定上游的非流式 JSON 请求；不跟随重定向，不暴露上游错误正文。 */
public class ModelHttp {
    private final ObjectMapper json;
    public ModelHttp(ObjectMapper json) { this.json = json; }
    public JsonNode request(String url, String key, JsonNode body, int timeout) throws IOException {
        HttpURLConnection c = (HttpURLConnection) URI.create(url).toURL().openConnection();
        c.setInstanceFollowRedirects(false);
        c.setConnectTimeout(4000);
        c.setReadTimeout(timeout);
        c.setRequestProperty("Content-Type", "application/json");
        if (!key.isEmpty()) c.setRequestProperty("Authorization", "Bearer " + key);
        try {
            if (body != null) {
                c.setRequestMethod("POST"); c.setDoOutput(true);
                try (OutputStream out = c.getOutputStream()) { json.writeValue(out, body); }
            }
            int code = c.getResponseCode();
            if (code < 200 || code >= 300) throw new IOException("模型服务返回 HTTP " + code);
            try (InputStream in = c.getInputStream(); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
                byte[] buffer = new byte[8192]; int n;
                while ((n = in.read(buffer)) != -1) {
                    if (out.size() + n > 8 * 1024 * 1024) throw new IOException("模型响应过大");
                    out.write(buffer, 0, n);
                }
                return json.readTree(out.toByteArray());
            }
        } finally { c.disconnect(); }
    }
}
