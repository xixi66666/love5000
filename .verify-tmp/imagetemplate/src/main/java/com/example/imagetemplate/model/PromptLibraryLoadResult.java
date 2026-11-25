package com.example.imagetemplate.model;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public class PromptLibraryLoadResult {

    private final List<PromptLibrarySource> sources;

    private final List<PromptLibraryEntry> entries;

    private final int errorCount;

    private final String message;

    public PromptLibraryLoadResult(List<PromptLibrarySource> sources,
                                   List<PromptLibraryEntry> entries,
                                   int errorCount,
                                   String message) {
        this.sources = immutableCopy(sources);
        this.entries = immutableCopy(entries);
        this.errorCount = errorCount;
        this.message = message == null ? "" : message;
    }

    public List<PromptLibrarySource> getSources() {
        return sources;
    }

    public List<PromptLibraryEntry> getEntries() {
        return entries;
    }

    public int getErrorCount() {
        return errorCount;
    }

    public String getMessage() {
        return message;
    }

    private static <T> List<T> immutableCopy(List<T> values) {
        if (values == null) {
            return Collections.emptyList();
        }
        return Collections.unmodifiableList(new ArrayList<T>(values));
    }
}
