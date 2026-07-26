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

@Component
public class ImagePromptTemplateAdapter {

    private static final int SUMMARY_LIMIT = 180;

    private static final Set<String> IMAGE_SOURCE_IDS = new HashSet<String>(Arrays.asList(
            "youmind-awesome-gpt-image-2",
            "freestylefly-awesome-gpt-image-2",
            "evolink-awesome-gpt-image-2-prompts"
    ));

    private static final List<String> IMAGE_KEYWORDS = Arrays.asList(
            "图片", "图像", "视觉", "海报", "摄影", "插画", "logo", "ui",
            "电商", "角色", "image", "photo", "poster", "illustration", "visual"
    );

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

    private String summary(String prompt) {
        String compact = value(prompt).replaceAll("\\s+", " ").trim();
        if (compact.length() <= SUMMARY_LIMIT) {
            return compact;
        }
        return compact.substring(0, SUMMARY_LIMIT - 1) + "…";
    }

    private String normalizeId(String value) {
        String normalized = normalize(value)
                .replaceAll("[^a-z0-9]+", "-")
                .replaceAll("(^-+|-+$)", "");
        return normalized.isEmpty() ? "unknown" : normalized;
    }

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

    private String normalize(String value) {
        return value(value).trim().toLowerCase(Locale.ROOT);
    }

    private String value(String value) {
        return value == null ? "" : value;
    }

    private boolean hasText(String value) {
        return value != null && !value.trim().isEmpty();
    }
}
