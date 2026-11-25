package com.example.website.integration.models;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/** 固定上游的非流式 JSON 请求；不跟随重定向，不暴露上游错误正文。 */
public class ModelHttp extends com.example.common.ai.ModelHttp {
    public ModelHttp(ObjectMapper json) { super(json); }

    JsonNode requestOpenCodeGo(String url, String key, JsonNode body, int timeout) throws IOException {
        Map<String, String> headers = new HashMap<>();
        headers.put("User-Agent", "love5000-website/1.0");
        // 模型网关每次接收完整消息，独立请求各自使用一个会话标识。
        headers.put("X-OpenCode-Session", "love5000-" + UUID.randomUUID());
        return request(url, key, body, timeout, false, headers);
    }

    JsonNode requestOpenCodeGoChat(String url, String key, JsonNode body, int timeout) throws IOException {
        return requestOpenCodeGo(url, key, body, timeout);
    }
}
