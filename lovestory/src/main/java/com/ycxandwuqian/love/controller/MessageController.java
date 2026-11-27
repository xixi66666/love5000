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

/**
 * 留言板（悄悄话）的 REST 接口。
 *
 * <p>挂在 {@code /api/messages} 下，提供读取、追加、清空三种操作。数据不落 MySQL，
 * 而是把整个留言数组以 JSON 文本读写一个文件（默认 {@code src/main/resources/static/message.txt}），
 * 因此没有分页、也不适合存放大量数据；文件缺失或内容为空白时按"没有留言"处理。</p>
 *
 * <p>三个读写方法都声明为 {@code synchronized}，同一实例内的并发请求被串行化，
 * 避免"读全量-追加-整体重写"互相覆盖。这是进程内锁，多实例部署时不保证一致性。</p>
 *
 * <p>留言文件位置在构造时探测（先按仓库根目录、再按模块目录解析），
 * 生产构造器把探测结果固化到 {@link #messageFile}，测试构造器可以直接指定临时文件。</p>
 */
@RestController
@RequestMapping("/api/messages")
public class MessageController {

    /** 单条留言的最大长度，按 Java 字符数（非字节）计，与前端提示一致。 */
    private static final int MAX_MESSAGE_LENGTH = 200;

    /** 留言数组的反序列化类型令牌，复用以免每次读取都重建泛型信息。 */
    private static final TypeReference<List<SecretMessage>> MESSAGE_LIST_TYPE =
            new TypeReference<List<SecretMessage>>() {
            };

    /** Spring 容器中的 Jackson 实例，保证留言 JSON 与全局序列化配置一致。 */
    private final ObjectMapper objectMapper;

    /** 留言文件的绝对路径；父目录或文件缺失时由读写前的兜底方法补建。 */
    private final Path messageFile;

    /**
     * 生产用构造器：按当前工作目录探测留言文件位置。
     *
     * @param objectMapper Spring 注入的 Jackson 实例
     */
    @Autowired
    public MessageController(ObjectMapper objectMapper) {
        this(objectMapper, resolveMessageFile());
    }

    /**
     * 测试用构造器：直接指定留言文件，绕过工作目录探测。
     *
     * @param objectMapper Spring 注入的 Jackson 实例
     * @param messageFile  留言文件路径，通常是临时目录下的文件
     */
    MessageController(ObjectMapper objectMapper, Path messageFile) {
        this.objectMapper = objectMapper;
        this.messageFile = messageFile;
    }

    /**
     * 读取全部留言。
     *
     * @return 正常时含 {@code success=true} 与 {@code messages} 数组；文件不可读或 JSON 损坏时
     *         返回 {@code success=false}、可读的错误说明以及空数组，
     *         这样页面仍能按统一结构渲染，只是看不到留言
     */
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

    /**
     * 追加一条留言并立即落盘。
     *
     * <p>校验顺序：先去空白判断是否为空，再判断长度上限；任一步不通过都只返回
     * {@code success=false} 与可读 message，不会触碰文件。通过后执行
     * "读全量-追加-整体重写"，时间戳取服务端当前时刻的 ISO-8601 字符串。</p>
     *
     * @param request 请求体，形如 {@code {"text": "..."}}；为 {@code null} 或缺少 text 时按空文本处理
     * @return 成功时额外携带 {@code data}（新留言的 text 与 date），失败时仅含 success 与 message
     */
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

    /**
     * 清空全部留言，实现方式是把文件整体重写为 {@code []}。
     *
     * <p>没有二次确认，也不保留历史；重复调用是幂等的。</p>
     *
     * @return 成功或失败的统一响应；文件不可写时返回 {@code success=false} 与异常摘要
     */
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

    /**
     * 读取并反序列化留言文件。
     *
     * @return 留言列表；文件内容为空白（刚创建或被手工清空）时返回空列表而不是抛错
     * @throws IOException 文件不可读，或内容不是合法的 JSON 数组
     */
    private List<SecretMessage> readMessages() throws IOException {
        ensureMessageFile();
        String content = new String(Files.readAllBytes(messageFile), StandardCharsets.UTF_8).trim();
        if (!StringUtils.hasText(content)) {
            return new ArrayList<SecretMessage>();
        }
        return objectMapper.readValue(content, MESSAGE_LIST_TYPE);
    }

    /**
     * 整体覆盖写入留言列表。
     *
     * <p>使用缩进格式输出并显式按 UTF-8 编码，既方便人工查看，也避免 Windows 默认编码
     * 把中文写成乱码。</p>
     *
     * @param messages 待写入的完整列表，通常包含本次新增的那一条
     * @throws IOException 文件不可写
     */
    private void writeMessages(List<SecretMessage> messages) throws IOException {
        ensureMessageFile();
        String content = objectMapper.writerWithDefaultPrettyPrinter().writeValueAsString(messages);
        Files.write(messageFile, content.getBytes(StandardCharsets.UTF_8));
    }

    /**
     * 保证留言文件及其父目录存在，缺失时先写入空数组占位。
     *
     * @throws IOException 目录创建或占位文件写入失败（例如只读工作目录）
     */
    private void ensureMessageFile() throws IOException {
        Path parent = messageFile.getParent();
        if (parent != null) {
            Files.createDirectories(parent);
        }
        if (!Files.exists(messageFile)) {
            Files.write(messageFile, "[]".getBytes(StandardCharsets.UTF_8));
        }
    }

    /**
     * 探测留言文件的绝对路径。
     *
     * <p>三种启动方式的工作目录不同：以仓库根目录运行、以模块目录运行、或打包后运行。
     * 这里以"父目录是否存在"判断前两种；都命中不了时仍返回根目录版本，
     * 由 {@link #ensureMessageFile()} 在首次写入时补建目录，避免启动阶段直接失败。</p>
     *
     * @return 归一化后的绝对路径，返回值不保证文件已经存在
     */
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

    /**
     * 单条留言的内存表示：正文 {@code text} 与 ISO-8601 时间戳 {@code date}。
     *
     * <p>之所以继承 {@link LinkedHashMap} 而不是普通 POJO，是为了让 Jackson 直接把它序列化成
     * 扁平的 {@code {"text":..., "date":...}} 对象且字段顺序稳定；无参构造器供反序列化使用，
     * 双参构造器供新增留言时使用。</p>
     */
    public static class SecretMessage extends LinkedHashMap<String, String> {

        public SecretMessage() {
        }

        public SecretMessage(String text, String date) {
            put("text", text);
            put("date", date);
        }
    }
}
