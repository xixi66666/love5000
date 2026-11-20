package com.example.personalagent.service;

import com.example.personalagent.model.VaultNote;

import java.nio.file.*;
import java.util.*;
import java.util.regex.Pattern;

final class NoteLinks {
    static final Pattern WIKI = Pattern.compile("\\[\\[([^\\[\\]|#\\r\\n]*)(?:#([^\\[\\]|\\r\\n]+))?(?:\\|([^\\[\\]\\r\\n]+))?\\]\\]");
    private final Map<String,VaultNote> paths = new HashMap<>();
    private final Map<String,List<VaultNote>> suffixes = new HashMap<>();

    NoteLinks(List<VaultNote> notes) {
        for (VaultNote note : notes) {
            String path = normalized(note.path);
            paths.put(path, note);
            for (int slash = path.indexOf('/'); slash >= 0; slash = path.indexOf('/', slash + 1)) {
                suffixes.computeIfAbsent(path.substring(slash + 1), ignored -> new ArrayList<>()).add(note);
            }
        }
    }

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

    private static String normalized(String path) {
        return path.trim().toLowerCase(Locale.ROOT).replaceFirst("\\.md$", "");
    }
}
