package com.example.imagetemplate.service;

import com.example.imagetemplate.model.PromptLibraryCatalog;
import com.example.imagetemplate.model.PromptLibraryEntry;
import com.example.imagetemplate.model.PromptLibraryLoadResult;
import com.example.imagetemplate.model.PromptLibrarySource;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.core.io.ClassPathResource;
import org.springframework.core.io.Resource;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

@Component
public class PromptLibraryLoader {

    private static final String DEFAULT_RESOURCE =
            "templates/prompt-console/prompt-library.json";

    private static final int EXPECTED_ENTRY_COUNT = 4409;

    private final ObjectMapper objectMapper;

    public PromptLibraryLoader(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    public PromptLibraryLoadResult loadDefault() {
        return load(new ClassPathResource(DEFAULT_RESOURCE));
    }

    public PromptLibraryLoadResult load(Resource resource) {
        try {
            PromptLibraryCatalog catalog =
                    objectMapper.readValue(resource.getInputStream(), PromptLibraryCatalog.class);
            List<PromptLibrarySource> sources = safeSources(catalog);
            List<PromptLibraryEntry> rawEntries = safeEntries(catalog);
            List<PromptLibraryEntry> validEntries = new ArrayList<PromptLibraryEntry>();
            int invalidCount = 0;
            for (PromptLibraryEntry entry : rawEntries) {
                if (isValid(entry)) {
                    validEntries.add(entry);
                } else {
                    invalidCount++;
                }
            }

            List<String> messages = new ArrayList<String>();
            if (rawEntries.size() != EXPECTED_ENTRY_COUNT) {
                messages.add("大库条目数异常：预期 " + EXPECTED_ENTRY_COUNT
                        + "，实际 " + rawEntries.size());
            }
            if (invalidCount > 0) {
                messages.add("有 " + invalidCount + " 条记录缺少标题或 Prompt");
            }
            return new PromptLibraryLoadResult(
                    sources,
                    validEntries,
                    invalidCount,
                    join(messages));
        } catch (IOException | RuntimeException exception) {
            return new PromptLibraryLoadResult(
                    Collections.<PromptLibrarySource>emptyList(),
                    Collections.<PromptLibraryEntry>emptyList(),
                    1,
                    "大库资源解析失败：" + safeMessage(exception));
        }
    }

    private List<PromptLibrarySource> safeSources(PromptLibraryCatalog catalog) {
        if (catalog == null || catalog.getSources() == null) {
            return Collections.emptyList();
        }
        return catalog.getSources();
    }

    private List<PromptLibraryEntry> safeEntries(PromptLibraryCatalog catalog) {
        if (catalog == null || catalog.getEntries() == null) {
            return Collections.emptyList();
        }
        return catalog.getEntries();
    }

    private boolean isValid(PromptLibraryEntry entry) {
        return entry != null && hasText(entry.getTitle()) && hasText(entry.getPrompt());
    }

    private boolean hasText(String value) {
        return value != null && !value.trim().isEmpty();
    }

    private String join(List<String> messages) {
        StringBuilder joined = new StringBuilder();
        for (String message : messages) {
            if (joined.length() > 0) {
                joined.append("；");
            }
            joined.append(message);
        }
        return joined.toString();
    }

    private String safeMessage(Exception exception) {
        if (exception.getMessage() == null || exception.getMessage().trim().isEmpty()) {
            return exception.getClass().getSimpleName();
        }
        return exception.getMessage();
    }
}
