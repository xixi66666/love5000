package com.example.personalagent.service;

import com.example.personalagent.model.VaultNote;
import org.commonmark.Extension;
import org.commonmark.ext.gfm.tables.TablesExtension;
import org.commonmark.node.*;
import org.commonmark.parser.Parser;
import org.commonmark.renderer.html.HtmlRenderer;

import java.net.URI;
import java.net.URLEncoder;
import java.io.UnsupportedEncodingException;
import java.util.*;
import java.util.function.Consumer;
import java.util.regex.Matcher;

/**
 * 把 Markdown 笔记渲染成可安全内嵌的 HTML，并抽取其中的双链目标。
 *
 * <p>属服务的渲染工具，被 {@link VaultService#detail} 与 {@link VaultService#parse} 调用。
 * 渲染器启用 {@code escapeHtml} 与 {@code sanitizeUrls}：笔记里手写的 HTML、
 * {@code javascript:} 链接与远程图片都不会被原样输出——图片统一替换成占位文字，
 * 非 http(s) 链接被拆成纯文本，只保留站内 {@code #note=} 链接与外部 http(s) 链接。</p>
 *
 * <p>另外三处非显然行为：正文先截断到 {@link #MAX_PREVIEW}，只影响展示不影响存储；
 * 导入资料里 {@code ## AI 整理草稿} 之后的内容会去掉四空格缩进，使其按正常段落渲染；
 * 双链会被改写成指向本站阅读页的 {@code #note=} 链接，解析不到的目标保持原始字面量，
 * 让失效链接一眼可见。</p>
 */
final class NoteReading {
    /** 单篇渲染上限（字符）；超出部分由 {@link #truncated} 标记提示前端。 */
    private static final int MAX_PREVIEW = 120_000;
    // 解析器与渲染器无状态且线程安全，构建一次复用；表格扩展与 Vault 中的 .base 视图一致。
    private static final List<Extension> EXTENSIONS = Collections.singletonList(TablesExtension.create());
    private static final Parser PARSER = Parser.builder().extensions(EXTENSIONS).build();
    private static final HtmlRenderer RENDERER = HtmlRenderer.builder().extensions(EXTENSIONS)
        .escapeHtml(true).sanitizeUrls(true).build();

    /**
     * 渲染一篇笔记的正文。
     *
     * @param note  已解析的笔记，使用其 {@code body} 与 frontmatter 属性
     * @param links 与当前笔记集对应的双链解析器
     * @return 安全化后的 HTML 片段
     */
    static String render(VaultNote note, NoteLinks links) {
        String body = note.body.substring(0, Math.min(MAX_PREVIEW, note.body.length()));
        String draftMarker = "\n## AI 整理草稿\n\n";
        int draft = body.indexOf(draftMarker);
        if (draft >= 0 && "imported_document".equals(note.properties.get("record_type"))
            && "ai_generated".equals(note.properties.get("origin"))) {
            int text = draft + draftMarker.length();
            body = body.substring(0, text) + body.substring(text).replaceAll("(?m)^ {4}", "");
        }
        Node root = PARSER.parse(body);
        visit(root, node -> {
            if (node instanceof Text && !insideLink(node)) {
                renderWiki((Text) node, note, links);
            } else if (node instanceof Image) {
                node.insertBefore(new Text("[图片 · 在 Obsidian 或 Quartz 查看]"));
                node.unlink();
            } else if (node instanceof Link && !webLink(((Link)node).getDestination())) {
                while (node.getFirstChild() != null) node.insertBefore(node.getFirstChild());
                node.unlink();
            }
        });
        return RENDERER.render(root);
    }

    /** 正文是否超过渲染上限，前端据此提示「仅显示前若干字符」。 */
    static boolean truncated(VaultNote note) {
        return note.body.length() > MAX_PREVIEW;
    }

    /**
     * 抽取正文中的双链目标，保序去重。
     *
     * <p>只处理普通文本节点，跳过已在链接或图片中的内容，因此行内代码里的
     * {@code [[...]]} 不会被误当成双链。</p>
     *
     * @return 目标原文列表；没有双链时返回空列表
     */
    static List<String> targets(String body) {
        if (!body.contains("[[")) return Collections.emptyList();
        Set<String> links = new LinkedHashSet<>();
        visit(PARSER.parse(body), node -> {
            if (!(node instanceof Text) || insideLink(node)) return;
            Matcher matcher = NoteLinks.WIKI.matcher(((Text)node).getLiteral());
            while (matcher.find()) if (!matcher.group(1).trim().isEmpty()) links.add(matcher.group(1));
        });
        return new ArrayList<>(links);
    }

    /** 判断节点是否位于链接或图片内部，避免重复处理已结构化的内容。 */
    private static boolean insideLink(Node node) {
        for (Node parent = node.getParent(); parent != null; parent = parent.getParent()) {
            if (parent instanceof Link || parent instanceof Image) return true;
        }
        return false;
    }

    /** 迭代式深度优先遍历（显式栈，避免长笔记递归过深），访问顺序为文档序。 */
    private static void visit(Node root, Consumer<Node> action) {
        Deque<Node> pending = new ArrayDeque<>();
        pending.push(root);
        while (!pending.isEmpty()) {
            Node node = pending.pop();
            for (Node child = node.getLastChild(); child != null; child = child.getPrevious()) pending.push(child);
            action.accept(node);
        }
    }

    /**
     * 把一段文本里的所有双链改写成链接节点。
     *
     * <p>做法是边匹配边插入：每个命中点前后各插入纯文本或链接节点，最后删除原文本节点。
     * 解析不到目标的双链保留原始字面量，让读者知道链接失效；带标题锚点时一并编码成
     * {@code heading} 参数。</p>
     *
     * @param text  待处理的文本节点
     * @param note  所属笔记，用于相对路径解析
     * @param links 双链解析器
     */
    private static void renderWiki(Text text, VaultNote note, NoteLinks links) {
        String literal = text.getLiteral();
        Matcher match = NoteLinks.WIKI.matcher(literal);
        int start = 0;
        while (match.find()) {
            text.insertBefore(new Text(literal.substring(start, match.start())));
            String target = match.group(1).trim();
            String heading = match.group(2);
            String label = match.group(3) != null ? match.group(3) : target.isEmpty() ? heading : target;
            VaultNote resolved = links.resolve(note, target);
            if (resolved == null || label == null) {
                text.insertBefore(new Text(match.group()));
            } else {
                String url = "#note=" + encode(resolved.path) + (heading == null ? "" : "&heading=" + encode(heading));
                Link link = new Link(url, resolved.title);
                link.appendChild(new Text(label));
                text.insertBefore(link);
            }
            start = match.end();
        }
        if (start > 0) {
            text.insertBefore(new Text(literal.substring(start)));
            text.unlink();
        }
    }

    /**
     * 判断链接目标是否为可保留的网页地址。
     *
     * @return 仅当 scheme 为 http/https 且存在 host 时为 {@code true}；
     *         非法 URI 返回 {@code false}，随后该链接被拆成纯文本
     */
    private static boolean webLink(String destination) {
        try {
            URI uri = URI.create(destination);
            return ("https".equalsIgnoreCase(uri.getScheme()) || "http".equalsIgnoreCase(uri.getScheme())) && uri.getHost() != null;
        } catch (IllegalArgumentException invalid) {
            return false;
        }
    }

    /**
     * URL 编码链接参数。
     *
     * @return 以 {@code %20} 表示空格而不是 {@code +}，保证浏览器地址栏与服务端解码一致
     */
    private static String encode(String value) {
        try { return URLEncoder.encode(value, "UTF-8").replace("+","%20"); }
        catch (UnsupportedEncodingException impossible) { throw new IllegalStateException(impossible); }
    }
}
