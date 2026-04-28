package com.ycxandwuqian.love.controller;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/messages")
public class MessageController {

    private static final int MAX_MESSAGE_LENGTH = 200;
    private static final TypeReference<List<SecretMessage>> MESSAGE_LIST_TYPE =
            new TypeReference<List<SecretMessage>>() {
            };

    private final ObjectMapper objectMapper;
    private final Path messageFile;

    @Autowired
    public MessageController(ObjectMapper objectMapper) {
        this(objectMapper, resolveMessageFile());
    }

    MessageController(ObjectMapper objectMapper, Path messageFile) {
        this.objectMapper = objectMapper;
        this.messageFile = messageFile;
    }

    @GetMapping
    public synchronized Map<String, Object> listMessages() {
        Map<String, Object> response = new HashMap<String, Object>();
        try {
            response.put("success", true);
            response.put("messages", readMessages());
        } catch (IOException e) {
            response.put("success", false);
            response.put("message", "Failed to load messages: " + e.getMessage());
            response.put("messages", new ArrayList<SecretMessage>());
        }
        return response;
    }

    @PostMapping
    public synchronized Map<String, Object> saveMessage(@RequestBody Map<String, String> request) {
        Map<String, Object> response = new HashMap<String, Object>();
        String text = request == null ? "" : request.get("text");
        String normalizedText = StringUtils.hasText(text) ? text.trim() : "";

        if (!StringUtils.hasText(normalizedText)) {
            response.put("success", false);
            response.put("message", "Message text must not be blank");
            return response;
        }

        if (normalizedText.length() > MAX_MESSAGE_LENGTH) {
            response.put("success", false);
            response.put("message", "Message text must not exceed 200 characters");
            return response;
        }

        try {
            List<SecretMessage> messages = readMessages();
            SecretMessage message = new SecretMessage(normalizedText, Instant.now().toString());
            messages.add(message);
            writeMessages(messages);

            response.put("success", true);
            response.put("message", "Message saved");
            response.put("data", message);
        } catch (IOException e) {
            response.put("success", false);
            response.put("message", "Failed to save message: " + e.getMessage());
        }
        return response;
    }

    @DeleteMapping
    public synchronized Map<String, Object> clearMessages() {
        Map<String, Object> response = new HashMap<String, Object>();
        try {
            writeMessages(new ArrayList<SecretMessage>());
            response.put("success", true);
            response.put("message", "Messages cleared");
        } catch (IOException e) {
            response.put("success", false);
            response.put("message", "Failed to clear messages: " + e.getMessage());
        }
        return response;
    }

    private List<SecretMessage> readMessages() throws IOException {
        ensureMessageFile();
        String content = new String(Files.readAllBytes(messageFile), StandardCharsets.UTF_8).trim();
        if (!StringUtils.hasText(content)) {
            return new ArrayList<SecretMessage>();
        }
        return objectMapper.readValue(content, MESSAGE_LIST_TYPE);
    }

    private void writeMessages(List<SecretMessage> messages) throws IOException {
        ensureMessageFile();
        String content = objectMapper.writerWithDefaultPrettyPrinter().writeValueAsString(messages);
        Files.write(messageFile, content.getBytes(StandardCharsets.UTF_8));
    }

    private void ensureMessageFile() throws IOException {
        Path parent = messageFile.getParent();
        if (parent != null) {
            Files.createDirectories(parent);
        }
        if (!Files.exists(messageFile)) {
            Files.write(messageFile, "[]".getBytes(StandardCharsets.UTF_8));
        }
    }

    private static Path resolveMessageFile() {
        Path rootRunPath = Paths.get("lovestory", "src", "main", "resources", "static", "message.txt")
                .toAbsolutePath()
                .normalize();
        if (Files.exists(rootRunPath.getParent())) {
            return rootRunPath;
        }

        Path moduleRunPath = Paths.get("src", "main", "resources", "static", "message.txt")
                .toAbsolutePath()
                .normalize();
        if (Files.exists(moduleRunPath.getParent())) {
            return moduleRunPath;
        }

        return rootRunPath;
    }

    public static class SecretMessage extends LinkedHashMap<String, String> {

        public SecretMessage() {
        }

        public SecretMessage(String text, String date) {
            put("text", text);
            put("date", date);
        }
    }
}
