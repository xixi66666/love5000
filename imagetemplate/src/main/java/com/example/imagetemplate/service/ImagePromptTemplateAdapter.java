package com.example.imagetemplate.service;

import com.example.imagetemplate.model.ImagePromptTemplate;
import com.example.imagetemplate.model.PromptLibraryEntry;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * Prompt Console 大库到图片模板模型的适配层。
 *
 * <p>把大库条目（正常为 4409 条，降级时可能更少）转换成统一的 {@link ImagePromptTemplate}，
 * 与精选模板合并使用。负责三件容易出错的事：</p>
 * <ul>
 *   <li>生成跨构建稳定的唯一 ID：来源 + 原始 ID + 内容指纹 + 同指纹出现序号，
 *       保证大库重复内容既不丢条目也不会与精选模板撞 ID。</li>
 *   <li>判定图片相关性：三个图片专用来源无条件标记为图片相关，其余来源只按
 *       分类与标签关键词判定，不扫描 Prompt 正文。</li>
 *   <li>补齐展示字段：摘要由 Prompt 压缩裁剪而成，空分类/空来源名有中文兜底。</li>
 * </ul>
 *
 * <p>适配结果一律 {@code templateKind=DIRECT}、{@code curated=false}、
 * {@code jsonTemplate} 为空 Map——大库条目没有结构化模板，渲染时按直接提示词处理。</p>
 */
@Component
public class ImagePromptTemplateAdapter {

    /** 摘要截断长度（字符）；超出时保留该长度减一再加一个省略号，保证总长不超限。 */
    private static final int SUMMARY_LIMIT = 180;

    /** 图片专用提示词来源：这些来源的条目全部视为图片相关，不再做关键词判定。 */
    private static final Set<String> IMAGE_SOURCE_IDS = new HashSet<String>(Arrays.asList(
            "youmind-awesome-gpt-image-2",
            "freestylefly-awesome-gpt-image-2",
            "evolink-awesome-gpt-image-2-prompts"
    ));

    /** 通用来源的图片相关性关键词，匹配已小写化的分类与标签拼接串；含中英文两种写法。 */
    private static final List<String> IMAGE_KEYWORDS = Arrays.asList(
            "图片", "图像", "视觉", "海报", "摄影", "插画", "logo", "ui",
            "电商", "角色", "image", "photo", "poster", "illustration", "visual"
    );

    /**
     * 批量适配大库条目。
     *
     * <p>同一条 base ID 会按出现次序追加 {@code -2}、{@code -3} 后缀，避免大库中
     * 完全重复的条目在聚合列表里撞 ID。条目列表为 {@code null} 时返回空列表，
     * 单条为 {@code null} 时跳过，让上游的加载降级结果可以直接传入。</p>
     *
     * @param entries 大库原始条目，可为 {@code null}
     * @return 与条目顺序一致（跳过 {@code null} 后）的模板列表
     */
    public List<ImagePromptTemplate> adapt(List<PromptLibraryEntry> entries) {
        List<ImagePromptTemplate> templates = new ArrayList<ImagePromptTemplate>();
        Map<String, Integer> occurrences = new HashMap<String, Integer>();
        if (entries == null) {
            return templates;
        }
        for (PromptLibraryEntry entry : entries) {
            if (entry == null) {
                continue;
            }
            String baseId = baseId(entry);
            int occurrence = occurrences.containsKey(baseId)
                    ? occurrences.get(baseId) + 1
                    : 1;
            occurrences.put(baseId, occurrence);
            templates.add(adapt(entry, occurrence == 1 ? baseId : baseId + "-" + occurrence));
        }
        return templates;
    }

    /**
     * 单条条目的字段映射。
     *
     * <p>分类为空时归入“其他”；来源名为空时回退为来源 ID，保证前端分组不会出现空白项；
     * {@code categorySlug} 由分类名哈希派生（{@code library-category-} 加 12 位十六进制），
     * 因此同一分类在多次构建之间保持稳定，前端旧筛选参数不会因为重启失效。</p>
     *
     * @param entry 已通过校验（标题与 Prompt 非空）的条目
     * @param id    已消歧的模板 ID
     * @return 可直接参与聚合的模板对象
     */
    private ImagePromptTemplate adapt(PromptLibraryEntry entry, String id) {
        ImagePromptTemplate template = new ImagePromptTemplate();
        String category = hasText(entry.getCategory()) ? entry.getCategory().trim() : "其他";
        template.setId(id);
        template.setTitle(entry.getTitle().trim());
        template.setCategory(category);
        template.setCategorySlug("library-category-" + sha256(category).substring(0, 12));
        template.setSummary(summary(entry.getPrompt()));
        template.setTags(entry.getTags() == null
                ? new ArrayList<String>()
                : new ArrayList<String>(entry.getTags()));
        template.setJsonTemplate(new LinkedHashMap<String, Object>());
        template.setPromptTemplate(entry.getPrompt());
        template.setSourceUrl(entry.getSourceUrl());
        template.setSourceId(entry.getSourceId());
        template.setSourceName(hasText(entry.getSourceName())
                ? entry.getSourceName().trim()
                : entry.getSourceId());
        template.setTemplateKind("DIRECT");
        template.setImageRelated(isImageRelated(entry));
        template.setCurated(false);
        return template;
    }

    /**
     * 生成未消歧的模板 ID。
     *
     * <p>格式为 {@code library-<来源>-<原始ID>-<指纹前12位>}：来源与原始 ID 便于人工溯源，
     * 指纹覆盖来源、原始 ID、标题、分类与 Prompt，内容一旦变化 ID 随之变化，
     * 不会把新内容伪装成旧条目；代价是同一条目改了正文后旧链接会失效。</p>
     *
     * @param entry 大库条目
     * @return 未追加重复序号的基础 ID
     */
    private String baseId(PromptLibraryEntry entry) {
        String fingerprintInput = value(entry.getSourceId()) + "\n"
                + value(entry.getId()) + "\n"
                + value(entry.getTitle()) + "\n"
                + value(entry.getCategory()) + "\n"
                + value(entry.getPrompt());
        return "library-" + normalizeId(entry.getSourceId())
                + "-" + normalizeId(entry.getId())
                + "-" + sha256(fingerprintInput).substring(0, 12);
    }

    /**
     * 判定条目是否与图片生成相关。
     *
     * <p>先看来源：三个图片专用来源直接返回 {@code true}。其余来源只拼接分类与标签做
     * 关键词包含匹配，标题和 Prompt 正文不参与判定，避免长文本带来的误判和额外开销。</p>
     *
     * @param entry 大库条目
     * @return {@code true} 表示前端“仅图片”筛选会保留该条目
     */
    private boolean isImageRelated(PromptLibraryEntry entry) {
        String sourceId = normalize(entry.getSourceId());
        if (IMAGE_SOURCE_IDS.contains(sourceId)) {
            return true;
        }
        StringBuilder searchable = new StringBuilder(value(entry.getCategory()));
        if (entry.getTags() != null) {
            for (String tag : entry.getTags()) {
                searchable.append(' ').append(value(tag));
            }
        }
        String normalized = normalize(searchable.toString());
        for (String keyword : IMAGE_KEYWORDS) {
            if (normalized.contains(keyword)) {
                return true;
            }
        }
        return false;
    }

    /**
     * 由 Prompt 生成列表页摘要。
     *
     * <p>先把连续空白压成单个空格，再按 {@value #SUMMARY_LIMIT} 字符裁剪；超长时
     * 保留前 179 个字符并追加省略号，保证摘要总长不超过上限。大库 Prompt 可能上万字，
     * 列表接口只依赖该摘要，不能直接把原文塞进响应。</p>
     *
     * @param prompt 大库条目 Prompt，可为 {@code null}
     * @return 单行摘要，长度不超过 {@value #SUMMARY_LIMIT}
     */
    private String summary(String prompt) {
        String compact = value(prompt).replaceAll("\\s+", " ").trim();
        if (compact.length() <= SUMMARY_LIMIT) {
            return compact;
        }
        return compact.substring(0, SUMMARY_LIMIT - 1) + "…";
    }

    /**
     * 把来源或原始 ID 归一成小写连字符片段。
     *
     * <p>非字母数字字符（中文、空格、斜杠等）会折叠为单个连字符并去掉首尾连字符；
     * 结果为空时返回 {@code unknown}，避免拼出 {@code library---xxx} 这类歧义 ID。</p>
     *
     * @param value 原始片段，可为 {@code null}
     * @return 小写 slug 片段
     */
    private String normalizeId(String value) {
        String normalized = normalize(value)
                .replaceAll("[^a-z0-9]+", "-")
                .replaceAll("(^-+|-+$)", "");
        return normalized.isEmpty() ? "unknown" : normalized;
    }

    /**
     * 计算 UTF-8 文本的 SHA-256 十六进制摘要。
     *
     * <p>用于生成模板 ID 与分类 slug 的指纹部分；调用方各自截取前 12 位。</p>
     *
     * @param value 待摘要文本，{@code null} 按空串处理
     * @return 64 位小写十六进制字符串
     * @throws IllegalStateException JVM 不提供 SHA-256 时抛出（正常环境不会发生）
     */
    private String sha256(String value) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] bytes = digest.digest(value(value).getBytes(StandardCharsets.UTF_8));
            StringBuilder hex = new StringBuilder();
            for (byte item : bytes) {
                hex.append(String.format("%02x", item & 0xff));
            }
            return hex.toString();
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256 is unavailable", exception);
        }
    }

    /**
     * 空安全的去空白转小写。
     *
     * <p>固定使用 {@link Locale#ROOT}，避免土耳其语等区域把 {@code I} 转成
     * {@code ı} 导致同一分类在不同机器上哈希出不同 slug。</p>
     *
     * @param value 原始文本，可为 {@code null}
     * @return 去首尾空白后的小写文本；{@code null} 返回空串
     */
    private String normalize(String value) {
        return value(value).trim().toLowerCase(Locale.ROOT);
    }

    /**
     * 空安全的字符串取值。
     *
     * @param value 原始文本，可为 {@code null}
     * @return {@code null} 时返回空串，其余原样返回
     */
    private String value(String value) {
        return value == null ? "" : value;
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
}
