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

/**
 * {@link MessageController} 的单元测试。
 *
 * <p>通过包级构造器注入 {@code @TempDir} 下的临时留言文件，完全不触碰
 * {@code src/main/resources/static/message.txt}，因此用例之间互不影响、也不污染仓库。
 * 覆盖三条主线：追加后能读回且内容真正落盘、纯空白文本被拒绝、清空后列表为空。</p>
 */
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
