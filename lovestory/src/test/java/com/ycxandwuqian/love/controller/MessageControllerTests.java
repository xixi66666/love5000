package com.ycxandwuqian.love.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class MessageControllerTests {

    @TempDir
    Path tempDir;

    @Test
    void shouldSaveMessageToFileAndListIt() throws Exception {
        Path messageFile = tempDir.resolve("message.txt");
        MessageController controller = new MessageController(new ObjectMapper(), messageFile);
        Map<String, String> request = new HashMap<String, String>();
        request.put("text", "hello love");

        Map<String, Object> saveResponse = controller.saveMessage(request);
        Map<String, Object> listResponse = controller.listMessages();

        assertEquals(true, saveResponse.get("success"));
        assertEquals(true, listResponse.get("success"));
        List<?> messages = (List<?>) listResponse.get("messages");
        assertEquals(1, messages.size());
        assertTrue(new String(Files.readAllBytes(messageFile), StandardCharsets.UTF_8).contains("hello love"));
    }

    @Test
    void shouldRejectBlankMessage() {
        Path messageFile = tempDir.resolve("message.txt");
        MessageController controller = new MessageController(new ObjectMapper(), messageFile);
        Map<String, String> request = new HashMap<String, String>();
        request.put("text", "   ");

        Map<String, Object> response = controller.saveMessage(request);

        assertEquals(false, response.get("success"));
    }

    @Test
    void shouldClearMessages() {
        Path messageFile = tempDir.resolve("message.txt");
        MessageController controller = new MessageController(new ObjectMapper(), messageFile);
        Map<String, String> request = new HashMap<String, String>();
        request.put("text", "clear me");
        controller.saveMessage(request);

        Map<String, Object> clearResponse = controller.clearMessages();
        Map<String, Object> listResponse = controller.listMessages();

        assertEquals(true, clearResponse.get("success"));
        assertEquals(0, ((List<?>) listResponse.get("messages")).size());
    }
}
