package com.example.website.prompt.service;

import com.example.website.prompt.model.PromptSource;
import com.example.website.prompt.model.PromptSourceSnapshot;
import org.springframework.stereotype.Service;

import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

/**
 * 允许抓取的提示词来源白名单，内容硬编码在本类里。
 *
 * <p>新增来源等于改代码，这是刻意的安全边界：{@code /api/prompt-sources/refresh} 只在白名单内
 * 发起 HTTP 请求，请求参数无法让服务端访问任意 URL。当前白名单包含 Prompt123 入口和五个
 * GitHub 上的提示词仓库。</p>
 *
 * <p>每个来源都带一份内置摘要，供“尚未刷新”和“抓取失败”两种情形兜底；
 * {@link #listSources()} 返回副本，避免调用方改到内部状态。</p>
 */
@Service
public class PromptSourceRegistry {

    /** 启动时一次性构造的不可变白名单；对外只通过 {@link #listSources()} 的副本暴露。 */
    private final List<PromptSource> sources;

    public PromptSourceRegistry() {
        this.sources = Collections.unmodifiableList(Arrays.asList(
                new PromptSource(
                        "prompt123",
                        "Prompt123",
                        "https://prompt123.cn/?utm_source=novatools.cn",
                        "website",
                        Arrays.asList("提示词网站", "导航", "实时抓取候选"),
                        "Prompt123 是提示词网站入口，适合查找不同场景的提示词写法，并作为实时抓取候选来源。"),
                new PromptSource(
                        "awesome-chatgpt-prompts",
                        "prompts.chat",
                        "https://github.com/f/awesome-chatgpt-prompts",
                        "general",
                        Arrays.asList("通用提示词", "角色", "文本任务"),
                        "prompts.chat / f/awesome-chatgpt-prompts 适合参考通用角色、任务设定和文本提示词结构。"),
                new PromptSource(
                        "awesome-prompts",
                        "awesome-prompts",
                        "https://github.com/ai-boost/awesome-prompts",
                        "prompt-engineering",
                        Arrays.asList("提示词工程", "框架", "最佳实践"),
                        "ai-boost/awesome-prompts 适合提炼提示词工程框架、结构化写法和多步骤任务约束。"),
                new PromptSource(
                        "youmind-awesome-gpt-image-2",
                        "YouMind GPT Image 2",
                        "https://github.com/YouMind-OpenLab/awesome-gpt-image-2",
                        "image-generation",
                        Arrays.asList("图片生成", "视觉案例", "GPT Image 2"),
                        "YouMind-OpenLab/awesome-gpt-image-2 适合参考图片生成场景、视觉风格和高质量画面描述。"),
                new PromptSource(
                        "freestylefly-awesome-gpt-image-2",
                        "freestylefly GPT Image 2",
                        "https://github.com/freestylefly/awesome-gpt-image-2",
                        "image-generation",
                        Arrays.asList("图片生成", "结构化模板", "Prompt-as-Code"),
                        "freestylefly/awesome-gpt-image-2 适合参考结构化图片提示词、变量模板和可复用字段。"),
                new PromptSource(
                        "evolink-awesome-gpt-image-2-prompts",
                        "EvoLinkAI GPT Image 2 Prompts",
                        "https://github.com/EvoLinkAI/awesome-gpt-image-2-prompts",
                        "image-generation",
                        Arrays.asList("图片生成", "商业视觉", "案例库"),
                        "EvoLinkAI/awesome-gpt-image-2-prompts 适合参考商业视觉、摄影质感和负面限制。")
        ));
    }

    /**
     * 列出全部白名单来源。
     *
     * @return 来源列表的副本，按注册顺序排列；修改它不会影响白名单
     */
    public List<PromptSource> listSources() {
        return new ArrayList<PromptSource>(sources);
    }

    /**
     * 按 id 查找白名单中的来源。
     *
     * @param sourceId 来源 id，允许 {@code null}
     * @return 命中时返回来源定义；{@code null} 或不在白名单时返回 {@code null}
     */
    public PromptSource findSource(String sourceId) {
        if (sourceId == null) {
            return null;
        }
        for (PromptSource source : sources) {
            if (source.getId().equals(sourceId)) {
                return source;
            }
        }
        return null;
    }

    /**
     * 生成来源的兜底快照，用于未刷新、抓取失败和白名单外 id 三种情况。
     *
     * <p>白名单内返回 {@code status=fallback} 加内置摘要，说明“正在使用内置摘要”；
     * 白名单外返回 {@code status=failed}，id、地址、分类留空，并在 {@code message} 里写明
     * “Source is not allowed”，让前端能区分“没抓到”和“根本不允许抓”。</p>
     *
     * @param sourceId 来源 id，允许 {@code null}
     * @return 非 {@code null} 的快照，时间戳取当前时刻
     */
    public PromptSourceSnapshot defaultSnapshot(String sourceId) {
        PromptSource source = findSource(sourceId);
        if (source == null) {
            return new PromptSourceSnapshot(sourceId, sourceId, "", "", Collections.<String>emptyList(),
                    "failed", "", OffsetDateTime.now(), "Source is not allowed: " + sourceId);
        }
        return new PromptSourceSnapshot(
                source.getId(),
                source.getName(),
                source.getUrl(),
                source.getType(),
                source.getTags(),
                "fallback",
                source.getDefaultSummary(),
                OffsetDateTime.now(),
                "Using built-in source summary.");
    }
}
