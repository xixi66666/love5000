package com.example.imagetemplate.service;

import com.example.imagetemplate.model.PromptLibraryCatalog;
import com.example.imagetemplate.model.PromptLibraryEntry;
import com.example.imagetemplate.model.PromptLibraryLoadResult;
import com.example.imagetemplate.model.PromptLibrarySource;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.core.io.ClassPathResource;
import org.springframework.core.io.Resource;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * Prompt Console 大库加载与校验组件。
 *
 * <p>从 classpath 读取构建期复制进来的 {@code templates/prompt-console/prompt-library.json}
 * （唯一源码是 website 模块的 {@code prompt-library.json}，本模块不维护副本），
 * 并把结果整理成可诊断的 {@link PromptLibraryLoadResult}。</p>
 *
 * <p>设计原则是“加载失败不抛异常”：文件缺失、JSON 非法、字段缺失都只体现在返回结果的
 * 消息与无效条目计数里，让 {@link ImagePromptTemplateService} 能带着精选模板继续启动，
 * 并以 {@code DEGRADED} 状态把预期数量、实际数量和原因暴露给页面。</p>
 *
 * <p>无效条目的判定只看标题与 Prompt 是否非空白；分类、标签缺失由适配层兜底，
 * 不在此处丢弃。</p>
 */
@Component
public class PromptLibraryLoader {

    /** 大库在 classpath 中的固定位置，由 Maven 构建从 website 唯一源复制而来。 */
    private static final String DEFAULT_RESOURCE =
            "templates/prompt-console/prompt-library.json";

    /** 大库预期条数；仅用于在数量不符时生成告警，不作为加载失败条件。 */
    private static final int EXPECTED_ENTRY_COUNT = 4409;

    /** Jackson 映射器，按大库模型反序列化。 */
    private final ObjectMapper objectMapper;

    /**
     * @param objectMapper Spring 容器中的 Jackson 映射器
     */
    public PromptLibraryLoader(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    /**
     * 加载 classpath 中的默认大库。
     *
     * @return 加载结果；资源缺失时返回带中文失败原因的空结果
     */
    public PromptLibraryLoadResult loadDefault() {
        return load(new ClassPathResource(DEFAULT_RESOURCE));
    }

    /**
     * 从任意资源加载大库。
     *
     * <p>处理流程：反序列化 → 取来源与条目（空字段按空列表处理）→ 逐条过滤无效条目并计数
     * → 汇总“条数异常”“缺标题或 Prompt”两类消息。条目总数与 {@value #EXPECTED_ENTRY_COUNT}
     * 不一致时只追加告警而不丢弃数据，因为大库本身可能已合法扩充。</p>
     *
     * <p>任何 {@code IOException} 或运行时异常（例如 JSON 结构完全不对）都会被捕获，
     * 返回空来源、空条目、{@code invalidCount=1} 和“大库资源解析失败：...”消息，
     * 让上层能够降级而不是让 Spring 启动失败。</p>
     *
     * @param resource 待读取的大库资源，通常来自 classpath
     * @return 加载结果，{@code message} 为中文分号拼接的诊断信息
     */
    public PromptLibraryLoadResult load(Resource resource) {
        try {
            PromptLibraryCatalog catalog =
                    objectMapper.readValue(resource.getInputStream(), PromptLibraryCatalog.class);
            List<PromptLibrarySource> sources = safeSources(catalog);
            List<PromptLibraryEntry> rawEntries = safeEntries(catalog);
            List<PromptLibraryEntry> validEntries = new ArrayList<PromptLibraryEntry>();
            int invalidCount = 0;
            for (PromptLibraryEntry entry : rawEntries) {
                if (isValid(entry)) {
                    validEntries.add(entry);
                } else {
                    invalidCount++;
                }
            }

            List<String> messages = new ArrayList<String>();
            if (rawEntries.size() != EXPECTED_ENTRY_COUNT) {
                messages.add("大库条目数异常：预期 " + EXPECTED_ENTRY_COUNT
                        + "，实际 " + rawEntries.size());
            }
            if (invalidCount > 0) {
                messages.add("有 " + invalidCount + " 条记录缺少标题或 Prompt");
            }
            return new PromptLibraryLoadResult(
                    sources,
                    validEntries,
                    invalidCount,
                    join(messages));
        } catch (IOException | RuntimeException exception) {
            return new PromptLibraryLoadResult(
                    Collections.<PromptLibrarySource>emptyList(),
                    Collections.<PromptLibraryEntry>emptyList(),
                    1,
                    "大库资源解析失败：" + safeMessage(exception));
        }
    }

    /**
     * 空安全的来源读取。
     *
     * @param catalog 反序列化结果，可为 {@code null}
     * @return 来源列表；缺失时返回空列表而非 {@code null}
     */
    private List<PromptLibrarySource> safeSources(PromptLibraryCatalog catalog) {
        if (catalog == null || catalog.getSources() == null) {
            return Collections.emptyList();
        }
        return catalog.getSources();
    }

    /**
     * 空安全的条目读取。
     *
     * @param catalog 反序列化结果，可为 {@code null}
     * @return 条目列表；缺失时返回空列表而非 {@code null}
     */
    private List<PromptLibraryEntry> safeEntries(PromptLibraryCatalog catalog) {
        if (catalog == null || catalog.getEntries() == null) {
            return Collections.emptyList();
        }
        return catalog.getEntries();
    }

    /**
     * 判定条目是否可用于渲染。
     *
     * <p>标题与 Prompt 都必须包含非空白字符；缺任一项的条目无法展示或生成，
     * 只计入无效数量，不进入聚合列表。</p>
     *
     * @param entry 大库条目，可为 {@code null}
     * @return {@code true} 表示可以进入聚合
     */
    private boolean isValid(PromptLibraryEntry entry) {
        return entry != null && hasText(entry.getTitle()) && hasText(entry.getPrompt());
    }

    /**
     * 判断字符串是否包含非空白字符。
     *
     * @param value 待判断文本，可为 {@code null}
     * @return {@code null} 或纯空白返回 {@code false}
     */
    private boolean hasText(String value) {
        return value != null && !value.trim().isEmpty();
    }

    /**
     * 用中文分号拼接诊断消息。
     *
     * @param messages 消息列表，可为空
     * @return 拼接结果；为空时返回空串
     */
    private String join(List<String> messages) {
        StringBuilder joined = new StringBuilder();
        for (String message : messages) {
            if (joined.length() > 0) {
                joined.append("；");
            }
            joined.append(message);
        }
        return joined.toString();
    }

    /**
     * 提取异常的可读描述。
     *
     * <p>部分解析异常（例如空指针）没有 message，此时用异常类名兜底，
     * 保证降级消息里始终能看到失败类型。</p>
     *
     * @param exception 捕获到的异常
     * @return 非空的中文或英文原因片段
     */
    private String safeMessage(Exception exception) {
        if (exception.getMessage() == null || exception.getMessage().trim().isEmpty()) {
            return exception.getClass().getSimpleName();
        }
        return exception.getMessage();
    }
}
