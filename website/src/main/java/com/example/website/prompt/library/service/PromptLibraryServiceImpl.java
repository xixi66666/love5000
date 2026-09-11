package com.example.website.prompt.library.service;

import com.example.website.prompt.library.dao.PromptLibraryDao;
import com.example.website.prompt.library.dto.PromptCreateRequest;
import com.example.website.prompt.library.dto.PromptCreateResponse;
import com.example.website.prompt.library.dto.PromptDetailResponse;
import com.example.website.prompt.library.dto.PromptListResponse;
import com.example.website.prompt.library.dto.PromptMetaResponse;
import com.example.website.prompt.library.dto.PromptSearchRequest;
import com.example.website.prompt.library.model.PromptCategoryStat;
import com.example.website.prompt.library.model.PromptEntry;
import com.example.website.prompt.library.model.PromptGroupStat;
import com.example.website.prompt.library.model.PromptSourceStat;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
public class PromptLibraryServiceImpl implements PromptLibraryService {

    private static final int DEFAULT_SIZE = 48;
    private static final int MAX_SIZE = 100;
    private static final int PREVIEW_CHARS = 200;
    private static final int MAX_TITLE = 512;
    private static final int MAX_CATEGORY = 128;
    private static final int MAX_PROMPT = 60000;
    private static final int MAX_TAGS = 1000;
    private static final int MAX_SOURCE_URL = 512;
    private static final int MAX_LICENSE = 255;
    private static final String MANUAL_SOURCE_ID = "manual";
    private static final String DEFAULT_GROUP = "other";

    private final PromptLibraryDao dao;

    public PromptLibraryServiceImpl(PromptLibraryDao dao) {
        this.dao = dao;
    }

    @Override
    public PromptMetaResponse meta() {
        List<PromptGroupStat> groupStats = dao.selectGroupCounts();
        List<PromptCategoryStat> categoryStats = dao.selectCategoryCounts();
        List<PromptSourceStat> sourceStats = dao.selectSourceStats();

        Map<String, List<PromptMetaResponse.CategorySummary>> categoriesByGroup = new HashMap<String, List<PromptMetaResponse.CategorySummary>>();
        for (PromptCategoryStat stat : categoryStats) {
            String key = stat.getGroupSlug();
            List<PromptMetaResponse.CategorySummary> list = categoriesByGroup.get(key);
            if (list == null) {
                list = new ArrayList<PromptMetaResponse.CategorySummary>();
                categoriesByGroup.put(key, list);
            }
            list.add(new PromptMetaResponse.CategorySummary(stat.getCategory(), stat.getCount()));
        }

        List<PromptMetaResponse.GroupSummary> groups = new ArrayList<PromptMetaResponse.GroupSummary>();
        for (PromptGroupStat stat : groupStats) {
            PromptMetaResponse.GroupSummary summary = new PromptMetaResponse.GroupSummary();
            summary.setSlug(stat.getSlug());
            summary.setName(stat.getName());
            summary.setCount(stat.getCount());
            List<PromptMetaResponse.CategorySummary> categories = categoriesByGroup.get(stat.getSlug());
            summary.setCategories(categories == null ? new ArrayList<PromptMetaResponse.CategorySummary>() : categories);
            groups.add(summary);
        }

        List<PromptMetaResponse.SourceSummary> sources = new ArrayList<PromptMetaResponse.SourceSummary>();
        for (PromptSourceStat stat : sourceStats) {
            PromptMetaResponse.SourceSummary summary = new PromptMetaResponse.SourceSummary();
            summary.setId(stat.getSourceId());
            summary.setName(stat.getName());
            summary.setStatus(stat.getStatus());
            summary.setCount(stat.getCount());
            summary.setLicense(stat.getLicense());
            summary.setSummary(stat.getSummary());
            sources.add(summary);
        }

        PromptMetaResponse response = new PromptMetaResponse();
        response.setTotal(dao.countAll());
        response.setGroups(groups);
        response.setSources(sources);
        return response;
    }

    @Override
    public PromptListResponse search(PromptSearchRequest request) {
        int page = Math.max(1, request.getPage());
        int size = Math.min(MAX_SIZE, Math.max(1, request.getSize()));
        String keyword = escapeLike(trimToNull(request.getKeyword()));
        String group = trimToNull(request.getGroup());
        String category = trimToNull(request.getCategory());
        String source = trimToNull(request.getSource());
        String status = trimToNull(request.getStatus());

        long total = dao.countByFilter(keyword, group, category, source, status);
        int offset = (page - 1) * size;
        List<PromptEntry> rows = dao.searchPage(keyword, group, category, source, status, offset, size);

        List<PromptListResponse.EntrySummary> summaries = new ArrayList<PromptListResponse.EntrySummary>();
        for (PromptEntry row : rows) {
            PromptListResponse.EntrySummary summary = new PromptListResponse.EntrySummary();
            summary.setId(row.getId());
            summary.setTitle(row.getTitle());
            summary.setCategory(row.getCategory());
            summary.setGroupSlug(row.getGroupSlug());
            summary.setGroupName(row.getGroupName());
            summary.setSourceName(row.getSourceName());
            summary.setTags(splitTags(row.getTags()));
            summary.setLicense(row.getLicense());
            summary.setStatus(row.getStatus());
            summary.setPreview(resolvePreview(row));
            summaries.add(summary);
        }

        PromptListResponse response = new PromptListResponse();
        response.setTotal(total);
        response.setPage(page);
        response.setSize(size);
        response.setEntries(summaries);
        return response;
    }

    @Override
    public PromptDetailResponse detail(Long id) {
        if (id == null) {
            return null;
        }
        PromptEntry row = dao.findById(id);
        if (row == null) {
            return null;
        }
        PromptDetailResponse response = new PromptDetailResponse();
        response.setEntry(toEntryDetail(row));
        return response;
    }

    @Override
    public PromptCreateResponse create(PromptCreateRequest request) {
        if (request == null) {
            throw new IllegalArgumentException("请求体不能为空");
        }
        String title = requireTrimmed(request.getTitle(), "标题不能为空", MAX_TITLE);
        String category = requireTrimmed(request.getCategory(), "小分类不能为空", MAX_CATEGORY);
        String prompt = requireTrimmed(request.getPrompt(), "提示词正文不能为空", MAX_PROMPT);
        String tags = normalizeTags(request.getTags());
        String sourceUrl = trimToLength(request.getSourceUrl(), MAX_SOURCE_URL);
        String license = trimToLength(request.getLicense(), MAX_LICENSE);

        String groupSlug = dao.findGroupSlugByCategory(category);
        if (groupSlug == null || groupSlug.isEmpty()) {
            groupSlug = DEFAULT_GROUP;
        }
        dao.upsertManualSource();

        PromptEntry entry = new PromptEntry();
        entry.setEntryKey(MANUAL_SOURCE_ID + "-" + UUID.randomUUID());
        entry.setSourceId(MANUAL_SOURCE_ID);
        entry.setTitle(title);
        entry.setCategory(category);
        entry.setGroupSlug(groupSlug);
        entry.setPrompt(prompt);
        entry.setTags(tags);
        entry.setLicense(license);
        entry.setStatus("imported");
        entry.setSourceUrl(sourceUrl);
        dao.insert(entry);

        PromptCreateResponse response = new PromptCreateResponse();
        response.setEntry(toEntryDetail(dao.findById(entry.getId())));
        return response;
    }

    private PromptDetailResponse.EntryDetail toEntryDetail(PromptEntry row) {
        if (row == null) {
            return null;
        }
        PromptDetailResponse.EntryDetail detail = new PromptDetailResponse.EntryDetail();
        detail.setId(row.getId());
        detail.setTitle(row.getTitle());
        detail.setCategory(row.getCategory());
        detail.setGroupSlug(row.getGroupSlug());
        detail.setGroupName(row.getGroupName());
        detail.setSourceName(row.getSourceName());
        detail.setSourceUrl(row.getSourceUrl());
        detail.setTags(splitTags(row.getTags()));
        detail.setLicense(row.getLicense());
        detail.setStatus(row.getStatus());
        detail.setPrompt(row.getPrompt());
        return detail;
    }

    private String requireTrimmed(String value, String message, int max) {
        String trimmed = trimToNull(value);
        if (trimmed == null) {
            throw new IllegalArgumentException(message);
        }
        if (trimmed.length() > max) {
            throw new IllegalArgumentException(message + "，长度不能超过 " + max + " 个字符");
        }
        return trimmed;
    }

    private String trimToLength(String value, int max) {
        String trimmed = trimToNull(value);
        if (trimmed == null) {
            return "";
        }
        return trimmed.length() > max ? trimmed.substring(0, max) : trimmed;
    }

    private String normalizeTags(String value) {
        if (value == null || value.trim().isEmpty()) {
            return "";
        }
        List<String> tags = new ArrayList<String>();
        for (String tag : value.split("[,，]")) {
            String trimmed = tag.trim();
            if (!trimmed.isEmpty() && !tags.contains(trimmed)) {
                tags.add(trimmed);
            }
        }
        return String.join(",", tags);
    }

    private List<String> splitTags(String tags) {
        List<String> result = new ArrayList<String>();
        if (tags == null || tags.trim().isEmpty()) {
            return result;
        }
        for (String tag : tags.split(",")) {
            String trimmed = tag.trim();
            if (!trimmed.isEmpty()) {
                result.add(trimmed);
            }
        }
        return result;
    }

    private String resolvePreview(PromptEntry row) {
        if (row.getPreview() != null && !row.getPreview().isEmpty()) {
            return row.getPreview();
        }
        return trimPreview(row.getPrompt(), PREVIEW_CHARS);
    }

    private String trimPreview(String prompt, int max) {
        if (prompt == null) {
            return "";
        }
        String normalized = prompt.replace("\r\n", "\n");
        if (normalized.length() <= max) {
            return normalized;
        }
        return normalized.substring(0, max);
    }

    private String trimToNull(String value) {
        if (value == null) {
            return null;
        }
        String trimmed = value.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }

    private String escapeLike(String value) {
        if (value == null) {
            return null;
        }
        return value
                .replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_");
    }
}