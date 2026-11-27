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

/**
 * 提示词模板拼装服务：把用户给出的场景扩写成通用、图片、视频、海报、短提示词等多个版本。
 *
 * <p>不调用大模型、不访问网络，输出完全由固定中文模板拼接而成。它只依赖
 * {@link PromptSourceRegistry} 的白名单和 {@link PromptSourceFetchService} 的内存快照，
 * 因此同一个输入在快照不变时结果稳定可复现。</p>
 *
 * <p>选中来源会以“参考来源综合”前缀出现在每个版本前面，内容取自快照的名称、标签与摘要。
 * 快照为 {@code fallback}/{@code failed} 时同样可用，只是用了内置摘要。其他非显然规则：
 * {@code purpose} 决定第一个版本的类型，其余按固定顺序补齐且不重复；
 * {@code copywriting}/{@code ui}/{@code character} 等旧取值统一归一化为通用版；
 * 请求的来源全部无效时静默回退为全部来源，而不是报错。</p>
 */
@Service
public class PromptComposeService {

    /** 版本补齐顺序：purpose 指定的类型排在最前，其余按此顺序追加。 */
    private static final List<String> DEFAULT_ORDER = Arrays.asList("general", "image", "video", "poster", "short");

    private final PromptSourceRegistry registry;
    private final PromptSourceFetchService fetchService;

    public PromptComposeService(PromptSourceRegistry registry, PromptSourceFetchService fetchService) {
        this.registry = registry;
        this.fetchService = fetchService;
    }

    /**
     * 为一个场景生成多个候选提示词版本。
     *
     * <p>先补齐缺省值（语气、长度），再把来源 id 白名单化并提取指导信息，最后按
     * {@link #orderedTypes} 的顺序逐个渲染。来源快照只读一次，避免同一请求里多次读取缓存。</p>
     *
     * @param request 拼装请求，{@code scene} 去空白后不得为空
     * @return 固定 5 个版本（通用、图片、视频、海报、短提示词），顺序由 {@code purpose} 决定；
     *         每个版本都带类型、标题、正文、来源 id 与结构要素
     * @throws IllegalArgumentException {@code request} 为 {@code null} 或场景为空时抛出
     */
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

    /**
     * 按类型渲染一个版本，并为它挂上结构要素说明。
     *
     * <p>未知类型不会报错，会落到通用版模板，因此 {@link #orderedTypes} 新增取值时不必同时改这里。</p>
     *
     * @param type      版本类型，取值来自 {@link #DEFAULT_ORDER}
     * @param scene     用户场景，已去空白
     * @param tone      语气描述，已带缺省值
     * @param length    期望长度描述，仅通用版和图片版会用到
     * @param sourceIds 参与拼装的来源 id，原样写进结果
     * @param guidance  来源指导信息，可能为空（为空时不加前缀）
     * @return 渲染好的版本，不为 {@code null}
     */
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

    /**
     * 从内存快照中提取选中来源的名称与指导信号。
     *
     * <p>信号由标签和摘要组成：摘要截断到 96 字，最后统一去重并最多保留 8 条，避免前缀过长
     * 淹没正文。未在 {@code sourceIds} 里的快照会被跳过。</p>
     *
     * @param sourceIds 已白名单化的来源 id 列表，不会为 {@code null}
     * @return 名称与信号集合；来源存在但既没有名称也没有信号时两个集合都可能为空
     */
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

    /**
     * 在正文前拼接来源综合说明。
     *
     * @param guidance 来源指导信息
     * @param prompt   原始模板正文
     * @return 有可用指导信息时返回带前缀的正文，否则原样返回 {@code prompt}
     */
    private String withGuidance(SourceGuidance guidance, String prompt) {
        if (guidance.isEmpty()) {
            return prompt;
        }
        return "参考来源综合："
                + "对照 " + join(guidance.sourceNames, "、")
                + "，提取方法论：" + join(guidance.signals, "；")
                + "。\n" + prompt;
    }

    /**
     * 通用增强版模板：要求结构化描述主体、场景、风格、质量与限制，并固定排除品牌、乱码、水印等噪音。
     *
     * @param scene  用户场景
     * @param tone   语气描述
     * @param length 期望长度描述，原样嵌入模板
     * @return 通用版提示词正文
     */
    private String generalPrompt(String scene, String tone, String length) {
        return "围绕“" + scene + "”生成一个高质量提示词。"
                + "明确主体、环境、时间、情绪和关键细节，整体语气保持" + tone + "。"
                + "使用结构化描述组织主体、场景、风格、质量要求和限制条件，输出长度为" + length + "。"
                + "避免加入未指定品牌、无关人物、乱码文字、水印或重复元素。";
    }

    /**
     * 图片生成版模板：强调镜头语言、光线、构图与材质，并在末尾列出乱码、水印、肢体变形等负面限制。
     *
     * @param scene  用户场景
     * @param tone   语气/风格描述
     * @param length 期望长度描述
     * @return 图片版提示词正文
     */
    private String imagePrompt(String scene, String tone, String length) {
        return "生成一张高质量图片：“" + scene + "”。"
                + "主体清晰，场景具有明确空间层次，使用适合主题的镜头语言、自然光线设计和稳定构图。"
                + "补充材质、色彩、景深、氛围和细节密度，整体风格保持" + tone + "，输出长度为" + length + "。"
                + "不要出现乱码文字、水印、额外 logo、多余手指、变形肢体、错误透视或与场景无关的元素。";
    }

    /**
     * 视频分镜版模板：固定三镜头结构（建立场景 → 追逐推进 → 收束瞬间），每镜头都描述运镜、
     * 节奏、光线和声音，末尾给出连续性与负面限制。
     *
     * @param scene 用户场景
     * @param tone  语气/风格描述
     * @return 三镜头分镜正文，含换行分段
     */
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

    /**
     * 商业海报版模板：要求第一眼有吸引点、主体与卖点层级清楚，并排除未授权品牌与价格信息。
     *
     * @param scene 用户场景
     * @param tone  语气/风格描述
     * @return 海报主视觉正文
     */
    private String posterPrompt(String scene, String tone) {
        return "围绕“" + scene + "”生成商业海报主视觉提示词。"
                + "画面需要第一眼有明确吸引点，主体和卖点层级清楚，构图适合封面或宣传图。"
                + "使用克制但有科技感的视觉语言，语气保持" + tone + "。"
                + "不要添加未授权品牌、价格、乱码文字、水印或干扰主视觉的装饰。";
    }

    /**
     * 短提示词版模板：单行拼出场景、语气和基础质量要求，适合输入框有长度限制的场景。
     *
     * @param scene 用户场景
     * @param tone  语气/风格描述
     * @return 单行提示词正文
     */
    private String shortPrompt(String scene, String tone) {
        return scene + "，" + tone + "，主体清晰，场景完整，光线自然，构图稳定，细节可信，不要乱码文字、水印、额外 logo 或无关元素。";
    }

    /**
     * 计算版本类型顺序：{@code purpose} 对应的类型排第一，再按 {@link #DEFAULT_ORDER} 补齐。
     *
     * <p>用 {@link LinkedHashSet} 去重，保证 purpose 指定的类型不会被重复渲染，
     * 返回顺序同时决定前端看到的候选顺序。</p>
     *
     * @param purpose 已归一化的用途，可能为 {@code general}/{@code image}/{@code video}/{@code poster}
     * @return 至少 5 个元素的有序类型列表
     */
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

    /**
     * 归一化用途取值。
     *
     * <p>空值回退为 {@code general}；{@code copywriting}、{@code ui}、{@code character} 这些旧前端
     * 取值也映射到 {@code general}，其余取值原样返回（由 {@link #orderedTypes} 决定是否命中专用模板）。</p>
     *
     * @param purpose 原始用途，允许 {@code null}
     * @return 可用于决定模板顺序的用途标识
     */
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

    /**
     * 把请求里的来源 id 收敛到白名单内。
     *
     * <p>三种情况：未指定来源时返回全部白名单；指定了但全部无效时同样回退为全部白名单
     * （保证结果里始终有来源可引用，而不是空列表）；部分有效时只保留有效的那些，顺序不变。</p>
     *
     * @param requestedSourceIds 请求中的来源 id，允许 {@code null}
     * @return 非空的白名单来源 id 列表
     */
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

    /**
     * 去重并限制条数，保持首次出现顺序。
     *
     * @param values 待处理文本，允许包含空白项
     * @param limit  最多保留的条数；达到上限立即结束，不再遍历剩余元素
     * @return 去空白、去重后的列表，长度不超过 {@code limit}
     */
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

    /**
     * 按长度截断文本并追加省略号，用于压缩来源摘要。
     *
     * <p>只在超长时追加 {@code "..."}，因此返回长度最多是 {@code maxLength + 3}。</p>
     *
     * @param value     原始文本，调用方已保证非空白
     * @param maxLength 截断前保留的字符数
     * @return 去空白后的文本或截断结果
     */
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

    /**
     * 承载一次拼装用到的来源指导信息。
     *
     * <p>{@link #isEmpty()} 在名称或信号任一为空时返回 {@code true}：只有名称没有方法信号、
     * 或只有信号没有名称时，都不会生成“参考来源综合”前缀，避免出现半句话。</p>
     */
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
