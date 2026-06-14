package com.example.website.prompt.service;

import com.example.website.prompt.dto.PromptComposeRequest;
import com.example.website.prompt.model.PromptSource;
import com.example.website.prompt.model.PromptSourceSnapshot;
import com.example.website.prompt.model.PromptVariant;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

@Service
public class PromptComposeService {

    private static final List<String> DEFAULT_ORDER = Arrays.asList("general", "image", "video", "poster", "short");

    private final PromptSourceRegistry registry;
    private final PromptSourceFetchService fetchService;

    public PromptComposeService(PromptSourceRegistry registry, PromptSourceFetchService fetchService) {
        this.registry = registry;
        this.fetchService = fetchService;
    }

    public List<PromptVariant> compose(PromptComposeRequest request) {
        if (request == null || isBlank(request.getScene())) {
            throw new IllegalArgumentException("场景不能为空");
        }

        String scene = request.getScene().trim();
        String purpose = normalizePurpose(request.getPurpose());
        String tone = isBlank(request.getTone()) ? "专业、清晰、有画面感" : request.getTone().trim();
        String length = isBlank(request.getLength()) ? "balanced" : request.getLength().trim();
        List<String> sourceIds = resolveSourceIds(request.getSourceIds());
        SourceGuidance guidance = buildSourceGuidance(sourceIds);

        List<String> order = orderedTypes(purpose);
        List<PromptVariant> variants = new ArrayList<PromptVariant>();
        for (String type : order) {
            variants.add(buildVariant(type, scene, tone, length, sourceIds, guidance));
        }
        return variants;
    }

    private PromptVariant buildVariant(String type,
                                       String scene,
                                       String tone,
                                       String length,
                                       List<String> sourceIds,
                                       SourceGuidance guidance) {
        if ("image".equals(type)) {
            return new PromptVariant("image", "图片生成版", withGuidance(guidance, imagePrompt(scene, tone, length)), sourceIds,
                    Arrays.asList("主体", "场景", "镜头", "光线", "构图", "负面限制"));
        }
        if ("video".equals(type)) {
            return new PromptVariant("video", "视频 / 分镜版", withGuidance(guidance, videoPrompt(scene, tone)), sourceIds,
                    Arrays.asList("分镜", "运动", "节奏", "连续性", "负面限制"));
        }
        if ("poster".equals(type)) {
            return new PromptVariant("poster", "商业海报版", withGuidance(guidance, posterPrompt(scene, tone)), sourceIds,
                    Arrays.asList("主视觉", "卖点", "层级", "构图", "限制"));
        }
        if ("short".equals(type)) {
            return new PromptVariant("short", "短提示词版", withGuidance(guidance, shortPrompt(scene, tone)), sourceIds,
                    Arrays.asList("核心场景", "风格", "限制"));
        }
        return new PromptVariant("general", "通用增强版", withGuidance(guidance, generalPrompt(scene, tone, length)), sourceIds,
                Arrays.asList("主体", "场景", "风格", "质量", "限制"));
    }

    private SourceGuidance buildSourceGuidance(List<String> sourceIds) {
        List<PromptSourceSnapshot> snapshots = fetchService.listSnapshots();
        List<String> selectedNames = new ArrayList<String>();
        List<String> selectedSignals = new ArrayList<String>();
        for (PromptSourceSnapshot snapshot : snapshots) {
            if (!sourceIds.contains(snapshot.getSourceId())) {
                continue;
            }
            if (!isBlank(snapshot.getName())) {
                selectedNames.add(snapshot.getName());
            }
            appendAll(selectedSignals, snapshot.getTags());
            if (!isBlank(snapshot.getSummary())) {
                selectedSignals.add(limit(snapshot.getSummary(), 96));
            }
        }
        return new SourceGuidance(selectedNames, dedupeAndLimit(selectedSignals, 8));
    }

    private String withGuidance(SourceGuidance guidance, String prompt) {
        if (guidance.isEmpty()) {
            return prompt;
        }
        return "参考来源综合："
                + "对照 " + join(guidance.sourceNames, "、")
                + "，提取方法论：" + join(guidance.signals, "；")
                + "。\n" + prompt;
    }

    private String generalPrompt(String scene, String tone, String length) {
        return "围绕“" + scene + "”生成一个高质量提示词。"
                + "明确主体、环境、时间、情绪和关键细节，整体语气保持" + tone + "。"
                + "使用结构化描述组织主体、场景、风格、质量要求和限制条件，输出长度为" + length + "。"
                + "避免加入未指定品牌、无关人物、乱码文字、水印或重复元素。";
    }

    private String imagePrompt(String scene, String tone, String length) {
        return "生成一张高质量图片：“" + scene + "”。"
                + "主体清晰，场景具有明确空间层次，使用适合主题的镜头语言、自然光线设计和稳定构图。"
                + "补充材质、色彩、景深、氛围和细节密度，整体风格保持" + tone + "，输出长度为" + length + "。"
                + "不要出现乱码文字、水印、额外 logo、多余手指、变形肢体、错误透视或与场景无关的元素。";
    }

    private String videoPrompt(String scene, String tone) {
        return "为“" + scene + "”生成可直接用于视频生成的三镜头分镜提示词，整体风格保持" + tone + "。"
                + "\n镜头 1：建立场景。画面从低机位缓慢推进到“" + scene + "”，主体首次入画，动作清楚自然；"
                + "镜头使用轻微推镜和稳定跟拍，节奏轻快，光线柔和明亮，声音包含环境底噪和主体细小动作声。"
                + "\n镜头 2：追逐推进。主体沿画面纵深移动，关键动作连续展开，镜头横向跟拍并轻微摇镜保持主体居中；"
                + "节奏加快但不跳切，光线保持前一镜头的方向和色温，声音强化脚步、风声或翅膀振动等运动细节。"
                + "\n镜头 3：收束瞬间。主体在画面前景停下或轻轻跃起，视线和动作落到目标上，镜头慢慢靠近形成温柔定格；"
                + "节奏放缓，光线更柔和，声音从运动声过渡到安静环境声，保留角色、空间、色彩和叙事连续性。"
                + "\n负面限制：避免跳切混乱、主体身份漂移、无意义运动、乱码文字、水印、变形肢体和不真实素材边界。";
    }

    private String posterPrompt(String scene, String tone) {
        return "围绕“" + scene + "”生成商业海报主视觉提示词。"
                + "画面需要第一眼有明确吸引点，主体和卖点层级清楚，构图适合封面或宣传图。"
                + "使用克制但有科技感的视觉语言，语气保持" + tone + "。"
                + "不要添加未授权品牌、价格、乱码文字、水印或干扰主视觉的装饰。";
    }

    private String shortPrompt(String scene, String tone) {
        return scene + "，" + tone + "，主体清晰，场景完整，光线自然，构图稳定，细节可信，不要乱码文字、水印、额外 logo 或无关元素。";
    }

    private List<String> orderedTypes(String purpose) {
        Set<String> ordered = new LinkedHashSet<String>();
        if ("image".equals(purpose)) {
            ordered.add("image");
        } else if ("video".equals(purpose)) {
            ordered.add("video");
        } else if ("poster".equals(purpose)) {
            ordered.add("poster");
        } else {
            ordered.add("general");
        }
        ordered.addAll(DEFAULT_ORDER);
        return new ArrayList<String>(ordered);
    }

    private String normalizePurpose(String purpose) {
        if (isBlank(purpose)) {
            return "general";
        }
        String value = purpose.trim();
        if ("copywriting".equals(value) || "ui".equals(value) || "character".equals(value)) {
            return "general";
        }
        return value;
    }

    private List<String> resolveSourceIds(List<String> requestedSourceIds) {
        List<String> result = new ArrayList<String>();
        if (requestedSourceIds == null || requestedSourceIds.isEmpty()) {
            for (PromptSource source : registry.listSources()) {
                result.add(source.getId());
            }
            return result;
        }
        for (String sourceId : requestedSourceIds) {
            if (registry.findSource(sourceId) != null) {
                result.add(sourceId);
            }
        }
        if (result.isEmpty()) {
            for (PromptSource source : registry.listSources()) {
                result.add(source.getId());
            }
        }
        return result;
    }

    private boolean isBlank(String value) {
        return value == null || value.trim().isEmpty();
    }

    private void appendAll(List<String> target, List<String> values) {
        if (values == null) {
            return;
        }
        for (String value : values) {
            if (!isBlank(value)) {
                target.add(value.trim());
            }
        }
    }

    private List<String> dedupeAndLimit(List<String> values, int limit) {
        Set<String> unique = new LinkedHashSet<String>();
        for (String value : values) {
            if (!isBlank(value)) {
                unique.add(value.trim());
            }
            if (unique.size() >= limit) {
                break;
            }
        }
        return new ArrayList<String>(unique);
    }

    private String limit(String value, int maxLength) {
        String trimmed = value.trim();
        if (trimmed.length() <= maxLength) {
            return trimmed;
        }
        return trimmed.substring(0, maxLength) + "...";
    }

    private String join(List<String> values, String delimiter) {
        StringBuilder builder = new StringBuilder();
        for (String value : values) {
            if (builder.length() > 0) {
                builder.append(delimiter);
            }
            builder.append(value);
        }
        return builder.toString();
    }

    private static class SourceGuidance {

        private final List<String> sourceNames;
        private final List<String> signals;

        private SourceGuidance(List<String> sourceNames, List<String> signals) {
            this.sourceNames = sourceNames;
            this.signals = signals;
        }

        private boolean isEmpty() {
            return sourceNames.isEmpty() || signals.isEmpty();
        }
    }
}
