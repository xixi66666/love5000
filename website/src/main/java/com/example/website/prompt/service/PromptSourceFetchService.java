package com.example.website.prompt.service;

import com.example.website.prompt.model.PromptSource;
import com.example.website.prompt.model.PromptSourceSnapshot;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class PromptSourceFetchService {

    private final PromptSourceRegistry registry;
    private final PromptSourceSummaryService summaryService;
    private final PromptSourceHttpClient httpClient;
    private final Map<String, PromptSourceSnapshot> snapshots = new LinkedHashMap<String, PromptSourceSnapshot>();

    @Autowired
    public PromptSourceFetchService(PromptSourceRegistry registry,
                                    PromptSourceSummaryService summaryService,
                                    PromptSourceHttpClient httpClient) {
        this.registry = registry;
        this.summaryService = summaryService;
        this.httpClient = httpClient;
        for (PromptSource source : registry.listSources()) {
            snapshots.put(source.getId(), registry.defaultSnapshot(source.getId()));
        }
    }

    public PromptSourceFetchService(PromptSourceRegistry registry) {
        this(registry, new PromptSourceSummaryService(), url -> {
            throw new IllegalStateException("offline test client");
        });
    }

    public synchronized List<PromptSourceSnapshot> listSnapshots() {
        List<PromptSourceSnapshot> result = new ArrayList<PromptSourceSnapshot>();
        for (PromptSource source : registry.listSources()) {
            PromptSourceSnapshot snapshot = snapshots.get(source.getId());
            result.add(snapshot == null ? registry.defaultSnapshot(source.getId()) : snapshot);
        }
        return result;
    }

    public synchronized List<PromptSourceSnapshot> refresh(List<String> sourceIds) {
        List<String> ids = sourceIds;
        if (ids == null || ids.isEmpty()) {
            ids = new ArrayList<String>();
            for (PromptSource source : registry.listSources()) {
                ids.add(source.getId());
            }
        }

        List<PromptSourceSnapshot> result = new ArrayList<PromptSourceSnapshot>();
        for (String sourceId : ids) {
            PromptSource source = registry.findSource(sourceId);
            if (source == null) {
                result.add(registry.defaultSnapshot(sourceId));
                continue;
            }
            PromptSourceSnapshot snapshot = refreshAllowedSource(source);
            snapshots.put(source.getId(), snapshot);
            result.add(snapshot);
        }
        return Collections.unmodifiableList(result);
    }

    private PromptSourceSnapshot refreshAllowedSource(PromptSource source) {
        try {
            String content = httpClient.fetch(source.getUrl());
            String summary = summaryService.summarize(content);
            return new PromptSourceSnapshot(
                    source.getId(),
                    source.getName(),
                    source.getUrl(),
                    source.getType(),
                    source.getTags(),
                    "live",
                    summary,
                    java.time.OffsetDateTime.now(),
                    "Live source fetched.");
        } catch (RuntimeException exception) {
            PromptSourceSnapshot fallback = registry.defaultSnapshot(source.getId());
            fallback.setMessage("Live fetch failed: " + exception.getMessage() + ". Using built-in source summary.");
            return fallback;
        }
    }
}
