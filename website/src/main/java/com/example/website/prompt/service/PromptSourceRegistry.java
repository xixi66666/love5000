package com.example.website.prompt.service;

import com.example.website.prompt.model.PromptSource;
import com.example.website.prompt.model.PromptSourceSnapshot;
import org.springframework.stereotype.Service;

import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

@Service
public class PromptSourceRegistry {

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

    public List<PromptSource> listSources() {
        return new ArrayList<PromptSource>(sources);
    }

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
