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

final class NoteReading {
    private static final int MAX_PREVIEW = 120_000;
    private static final List<Extension> EXTENSIONS = Collections.singletonList(TablesExtension.create());
    private static final Parser PARSER = Parser.builder().extensions(EXTENSIONS).build();
    private static final HtmlRenderer RENDERER = HtmlRenderer.builder().extensions(EXTENSIONS)
        .escapeHtml(true).sanitizeUrls(true).build();

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

    static boolean truncated(VaultNote note) {
        return note.body.length() > MAX_PREVIEW;
    }

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

    private static boolean insideLink(Node node) {
        for (Node parent = node.getParent(); parent != null; parent = parent.getParent()) {
            if (parent instanceof Link || parent instanceof Image) return true;
        }
        return false;
    }

    private static void visit(Node root, Consumer<Node> action) {
        Deque<Node> pending = new ArrayDeque<>();
        pending.push(root);
        while (!pending.isEmpty()) {
            Node node = pending.pop();
            for (Node child = node.getLastChild(); child != null; child = child.getPrevious()) pending.push(child);
            action.accept(node);
        }
    }

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

    private static boolean webLink(String destination) {
        try {
            URI uri = URI.create(destination);
            return ("https".equalsIgnoreCase(uri.getScheme()) || "http".equalsIgnoreCase(uri.getScheme())) && uri.getHost() != null;
        } catch (IllegalArgumentException invalid) {
            return false;
        }
    }

    private static String encode(String value) {
        try { return URLEncoder.encode(value, "UTF-8").replace("+","%20"); }
        catch (UnsupportedEncodingException impossible) { throw new IllegalStateException(impossible); }
    }
}
