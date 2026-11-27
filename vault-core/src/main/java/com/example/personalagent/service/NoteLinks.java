package com.example.personalagent.service;

import com.example.personalagent.model.VaultNote;

import java.nio.file.*;
import java.util.*;
import java.util.regex.Pattern;

/**
 * 双链解析器：把 {@code [[目标]]} 形式的 Obsidian 链接对应到具体笔记。
 *
 * <p>属服务层的轻量索引，只针对一次请求构建（{@link VaultService} 在阅读与图谱接口里
 * 用当前笔记列表实例化），不缓存、不持有文件句柄，因此文件系统变化立刻反映到解析结果。</p>
 *
 * <p>解析顺序有意模仿 Obsidian：先按「相对当前笔记所在目录」找邻居，再退回全库精确路径，
 * 最后才按唯一文件名后缀匹配；后缀命中多于一篇时返回 {@code null} 而不是猜，
 * 避免把链接错误地指到同名的另一篇笔记。含协议前缀、反斜杠或以斜杠开头的目标一律不解析，
 * 防止被当成 URL 或越界路径。</p>
 */
final class NoteLinks {
    /** 双链语法：目标、可选 {@code #标题} 与可选 {@code |别名}；方括号、竖线、井号与换行不参与匹配。 */
    static final Pattern WIKI = Pattern.compile("\\[\\[([^\\[\\]|#\\r\\n]*)(?:#([^\\[\\]|\\r\\n]+))?(?:\\|([^\\[\\]\\r\\n]+))?\\]\\]");
    // paths 存小写去后缀的完整相对路径；suffixes 存每级目录截断后的后缀到笔记列表的映射。
    private final Map<String,VaultNote> paths = new HashMap<>();
    private final Map<String,List<VaultNote>> suffixes = new HashMap<>();

    /**
     * 基于给定笔记集建立两条索引。
     *
     * @param notes 当前仓库的全部笔记，顺序不影响解析结果
     */
    NoteLinks(List<VaultNote> notes) {
        for (VaultNote note : notes) {
            String path = normalized(note.path);
            paths.put(path, note);
            for (int slash = path.indexOf('/'); slash >= 0; slash = path.indexOf('/', slash + 1)) {
                suffixes.computeIfAbsent(path.substring(slash + 1), ignored -> new ArrayList<>()).add(note);
            }
        }
    }

    /**
     * 把链接目标解析成唯一一篇笔记。
     *
     * @param source 发起链接的笔记，提供相对目录
     * @param target 链接中的原始目标（大小写、{@code .md} 后缀均可）
     * @return 命中且唯一的笔记；空目标返回 {@code source} 自身，
     *         目标非法或存在多个同名候选时返回 {@code null}
     */
    VaultNote resolve(VaultNote source, String target) {
        String key = normalized(target);
        if (key.isEmpty()) return source;
        if (key.indexOf(':') >= 0 || key.indexOf('\\') >= 0 || key.startsWith("/")) return null;
        VaultNote exact = paths.get(key);
        if (key.contains("/") && exact != null) return exact;
        try {
            Path folder = Paths.get(source.path).getParent();
            Path relative = (folder == null ? Paths.get(key) : folder.resolve(key)).normalize();
            VaultNote neighbor = paths.get(normalized(relative.toString().replace('\\', '/')));
            if (neighbor != null) return neighbor;
        } catch (InvalidPathException invalid) {
            return null;
        }
        if (exact != null) return exact;
        List<VaultNote> matches = suffixes.get(key);
        return matches != null && matches.size() == 1 ? matches.get(0) : null;
    }

    /** 归一化路径：去空白、转小写、去掉末尾 {@code .md}，使比较不受平台大小写差异影响。 */
    private static String normalized(String path) {
        return path.trim().toLowerCase(Locale.ROOT).replaceFirst("\\.md$", "");
    }
}
