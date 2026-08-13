package com.example.imagetemplate.service;

import com.example.imagetemplate.dto.ImageTemplateMetaResponse;
import com.example.imagetemplate.dto.ImageTemplatePageResponse;
import com.example.imagetemplate.dto.ImageTemplateQuery;
import com.example.imagetemplate.dto.ImageTemplateSummaryResponse;
import com.example.imagetemplate.dto.PromptRenderRequest;
import com.example.imagetemplate.dto.TemplateCategoryResponse;
import com.example.imagetemplate.dto.TemplateFunctionCategoryResponse;
import com.example.imagetemplate.dto.TemplateFunctionSceneResponse;
import com.example.imagetemplate.dto.TemplateSourceResponse;
import com.example.imagetemplate.model.ImagePromptTemplate;
import com.example.imagetemplate.model.LibraryAggregationStatus;
import com.example.imagetemplate.model.PromptLibraryLoadResult;
import com.example.imagetemplate.model.PromptLibrarySource;
import com.example.imagetemplate.model.TemplateFunctionClassification;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

@Service
public class ImagePromptTemplateService {

    private static final int EXPECTED_CURATED_COUNT = 47;

    private static final int EXPECTED_LIBRARY_COUNT = 4409;

    private final List<ImagePromptTemplate> templates;

    private final Map<String, ImagePromptTemplate> templatesById;

    private final LibraryAggregationStatus aggregationStatus;

    private final List<TemplateSourceResponse> sources;

    private final List<TemplateFunctionCategoryResponse> functionCategories;

    private String curatedLoadMessage = "";

    public ImagePromptTemplateService(ObjectMapper objectMapper,
                                      PromptLibraryLoader promptLibraryLoader,
                                      ImagePromptTemplateAdapter adapter,
                                      TemplateFunctionClassifier functionClassifier) {
        List<ImagePromptTemplate> curated = loadCuratedTemplates(objectMapper);
        decorateCurated(curated);

        PromptLibraryLoadResult libraryResult = promptLibraryLoader.loadDefault();
        List<ImagePromptTemplate> imported = adapter.adapt(libraryResult.getEntries());

        List<ImagePromptTemplate> aggregated = new ArrayList<ImagePromptTemplate>();
        aggregated.addAll(curated);
        aggregated.addAll(imported);
        decorateFunctionalClassifications(aggregated, functionClassifier);
        this.templates = Collections.unmodifiableList(aggregated);
        this.templatesById = Collections.unmodifiableMap(indexById(aggregated));
        this.aggregationStatus =
                buildStatus(curated.size(), imported.size(), libraryResult);
        this.sources = Collections.unmodifiableList(
                buildSources(libraryResult.getSources(), aggregated));
        this.functionCategories = Collections.unmodifiableList(
                buildFunctionCategories(functionClassifier, aggregated));
    }

    public ImageTemplatePageResponse search(ImageTemplateQuery query) {
        ImageTemplateQuery actual = query == null ? new ImageTemplateQuery() : query;
        validate(actual);

        String normalizedSource = normalize(actual.getSource());
        String normalizedCategory = normalize(actual.getCategory());
        String normalizedFunctionCategory =
                normalize(actual.getFunctionCategory());
        String normalizedFunctionScene = normalize(actual.getFunctionScene());
        String normalizedKeyword = normalize(actual.getKeyword());
        List<ImagePromptTemplate> filtered = new ArrayList<ImagePromptTemplate>();
        for (ImagePromptTemplate template : templates) {
            if (!matchesSource(template, normalizedSource)
                    || !matchesCategory(template, normalizedCategory)
                    || !matchesFunctionCategory(template, normalizedFunctionCategory)
                    || !matchesFunctionScene(template, normalizedFunctionScene)
                    || (actual.isImageOnly() && !template.isImageRelated())
                    || !matchesKeyword(template, normalizedKeyword)) {
                continue;
            }
            filtered.add(template);
        }

        long fromLong = ((long) actual.getPage() - 1L) * actual.getSize();
        int fromIndex = fromLong >= filtered.size() ? filtered.size() : (int) fromLong;
        int toIndex = Math.min(filtered.size(), fromIndex + actual.getSize());
        List<ImageTemplateSummaryResponse> summaries =
                new ArrayList<ImageTemplateSummaryResponse>();
        for (ImagePromptTemplate template : filtered.subList(fromIndex, toIndex)) {
            summaries.add(ImageTemplateSummaryResponse.from(template));
        }

        ImageTemplatePageResponse response = new ImageTemplatePageResponse();
        response.setTotal(filtered.size());
        response.setPage(actual.getPage());
        response.setSize(actual.getSize());
        response.setHasMore(toIndex < filtered.size());
        response.setLibraryStatus(aggregationStatus.getStatus());
        response.setMessage(aggregationStatus.getMessage());
        response.setTemplates(summaries);
        return response;
    }

    public ImageTemplateMetaResponse getMeta() {
        ImageTemplateMetaResponse response = new ImageTemplateMetaResponse();
        response.setTotal(templates.size());
        response.setCuratedCount(aggregationStatus.getLoadedCuratedCount());
        response.setLibraryCount(aggregationStatus.getLoadedLibraryCount());
        response.setImageRelatedCount(countImageRelated());
        response.setStatus(aggregationStatus);
        response.setSources(new ArrayList<TemplateSourceResponse>(sources));
        response.setCategories(listCategories());
        response.setFunctionCategories(
                new ArrayList<TemplateFunctionCategoryResponse>(functionCategories));
        return response;
    }

    public List<ImagePromptTemplate> listTemplates(String category, String keyword) {
        String normalizedCategory = normalize(category);
        String normalizedKeyword = normalize(keyword);
        List<ImagePromptTemplate> result = new ArrayList<ImagePromptTemplate>();
        for (ImagePromptTemplate template : templates) {
            if (!matchesCategory(template, normalizedCategory)) {
                continue;
            }
            if (!matchesKeyword(template, normalizedKeyword)) {
                continue;
            }
            result.add(template);
        }
        return result;
    }

    public List<TemplateCategoryResponse> listCategories() {
        Map<String, TemplateCategoryResponse> categories =
                new LinkedHashMap<String, TemplateCategoryResponse>();
        for (ImagePromptTemplate template : templates) {
            TemplateCategoryResponse category = categories.get(template.getCategorySlug());
            if (category == null) {
                category = new TemplateCategoryResponse(
                        template.getCategory(), template.getCategorySlug(), 0);
                categories.put(template.getCategorySlug(), category);
            }
            category.setCount(category.getCount() + 1);
        }
        return new ArrayList<TemplateCategoryResponse>(categories.values());
    }

    public ImagePromptTemplate findById(String id) {
        ImagePromptTemplate template = templatesById.get(id);
        if (template == null) {
            throw new ImagePromptTemplateNotFoundException(id);
        }
        return template;
    }

    public String renderPrompt(String id, PromptRenderRequest request) {
        ImagePromptTemplate template = findById(id);
        Map<String, Object> variables = request == null ? null : request.getVariables();
        String extraInstruction = request == null ? null : request.getExtraInstruction();
        if ("DIRECT".equals(template.getTemplateKind())) {
            StringBuilder direct = new StringBuilder(template.getPromptTemplate().trim());
            if (variables != null && !variables.isEmpty()) {
                direct.append("\n\n用户变量：\n");
                appendMap(direct, variables, 0);
            }
            if (hasText(extraInstruction)) {
                direct.append("\n\n用户补充要求：").append(extraInstruction.trim());
            }
            return direct.toString();
        }

        Map<String, Object> resolvedTemplate =
                resolveTemplate(template.getJsonTemplate(), variables);
        StringBuilder prompt = new StringBuilder();
        prompt.append("图像生成任务：").append(template.getTitle()).append("\n\n");
        prompt.append("常规模板：").append(template.getPromptTemplate()).append("\n\n");
        prompt.append("请将下面的结构化 JSON 模板转化为一个自然、明确、可直接传入图像生成接口 prompt 字段的高质量提示词：\n");
        appendMap(prompt, resolvedTemplate, 0);
        if (hasText(extraInstruction)) {
            prompt.append("\n用户补充要求：").append(extraInstruction.trim()).append("\n");
        }
        prompt.append("\n输出要求：保持主体、风格、构图、材质、文字和限制条件一致；如模板包含精确文字，必须逐字准确；不要在图像中加入模板之外的水印、签名或额外文字。");
        return prompt.toString();
    }

    private List<ImagePromptTemplate> loadCuratedTemplates(ObjectMapper objectMapper) {
        try {
            return objectMapper.readValue(
                    new ClassPathResource("templates/image-prompt-templates.json").getInputStream(),
                    new TypeReference<List<ImagePromptTemplate>>() {
                    });
        } catch (IOException | RuntimeException exception) {
            curatedLoadMessage = "精选模板加载失败：" + exception.getMessage();
            return new ArrayList<ImagePromptTemplate>();
        }
    }

    private void decorateCurated(List<ImagePromptTemplate> curated) {
        for (ImagePromptTemplate template : curated) {
            template.setSourceId("curated");
            template.setSourceName("精选模板");
            template.setTemplateKind("direct-prompt".equals(template.getCategorySlug())
                    ? "DIRECT"
                    : "STRUCTURED");
            template.setImageRelated(true);
            template.setCurated(true);
        }
    }

    private void decorateFunctionalClassifications(
            List<ImagePromptTemplate> values,
            TemplateFunctionClassifier functionClassifier) {
        for (ImagePromptTemplate template : values) {
            TemplateFunctionClassification classification =
                    functionClassifier.classify(template);
            template.setFunctionCategory(classification.getCategoryName());
            template.setFunctionCategorySlug(classification.getCategorySlug());
            template.setFunctionScene(classification.getSceneName());
            template.setFunctionSceneSlug(classification.getSceneSlug());
        }
    }

    private List<TemplateFunctionCategoryResponse> buildFunctionCategories(
            TemplateFunctionClassifier functionClassifier,
            List<ImagePromptTemplate> values) {
        Map<String, Integer> categoryCounts = new LinkedHashMap<String, Integer>();
        Map<String, Integer> sceneCounts = new LinkedHashMap<String, Integer>();
        for (ImagePromptTemplate template : values) {
            increment(categoryCounts, template.getFunctionCategorySlug());
            increment(sceneCounts, template.getFunctionCategorySlug()
                    + "/" + template.getFunctionSceneSlug());
        }

        List<TemplateFunctionCategoryResponse> result =
                new ArrayList<TemplateFunctionCategoryResponse>();
        for (TemplateFunctionClassifier.CategoryDefinition category
                : functionClassifier.getCatalog()) {
            List<TemplateFunctionSceneResponse> scenes =
                    new ArrayList<TemplateFunctionSceneResponse>();
            for (TemplateFunctionClassifier.SceneDefinition scene
                    : category.getScenes()) {
                scenes.add(new TemplateFunctionSceneResponse(
                        scene.getName(),
                        scene.getSlug(),
                        count(sceneCounts, category.getSlug() + "/" + scene.getSlug())));
            }
            result.add(new TemplateFunctionCategoryResponse(
                    category.getName(),
                    category.getSlug(),
                    count(categoryCounts, category.getSlug()),
                    scenes));
        }
        return result;
    }

    private void increment(Map<String, Integer> counts, String key) {
        counts.put(key, counts.containsKey(key) ? counts.get(key) + 1 : 1);
    }

    private Map<String, ImagePromptTemplate> indexById(List<ImagePromptTemplate> values) {
        Map<String, ImagePromptTemplate> indexed =
                new LinkedHashMap<String, ImagePromptTemplate>();
        for (ImagePromptTemplate template : values) {
            if (indexed.containsKey(template.getId())) {
                throw new IllegalStateException("Duplicate aggregate template id: "
                        + template.getId());
            }
            indexed.put(template.getId(), template);
        }
        return indexed;
    }

    private LibraryAggregationStatus buildStatus(int curatedCount,
                                                 int libraryCount,
                                                 PromptLibraryLoadResult libraryResult) {
        List<String> messages = new ArrayList<String>();
        if (hasText(curatedLoadMessage)) {
            messages.add(curatedLoadMessage);
        }
        if (curatedCount != EXPECTED_CURATED_COUNT) {
            messages.add("精选模板预期 " + EXPECTED_CURATED_COUNT + "，实际 " + curatedCount);
        }
        if (hasText(libraryResult.getMessage())) {
            messages.add(libraryResult.getMessage());
        }
        if (libraryCount != EXPECTED_LIBRARY_COUNT) {
            messages.add("大库有效条目预期 " + EXPECTED_LIBRARY_COUNT
                    + "，实际 " + libraryCount);
        }

        LibraryAggregationStatus status = new LibraryAggregationStatus();
        status.setExpectedCuratedCount(EXPECTED_CURATED_COUNT);
        status.setLoadedCuratedCount(curatedCount);
        status.setExpectedLibraryCount(EXPECTED_LIBRARY_COUNT);
        status.setLoadedLibraryCount(libraryCount);
        status.setTotal(curatedCount + libraryCount);
        status.setMessage(join(messages));
        status.setStatus(messages.isEmpty() ? "READY" : "DEGRADED");
        return status;
    }

    private List<TemplateSourceResponse> buildSources(
            List<PromptLibrarySource> librarySources,
            List<ImagePromptTemplate> aggregated) {
        Map<String, Integer> counts = new LinkedHashMap<String, Integer>();
        for (ImagePromptTemplate template : aggregated) {
            String id = template.getSourceId();
            counts.put(id, counts.containsKey(id) ? counts.get(id) + 1 : 1);
        }

        List<TemplateSourceResponse> result = new ArrayList<TemplateSourceResponse>();
        result.add(new TemplateSourceResponse(
                "curated", "精选模板", "", count(counts, "curated")));
        if (librarySources != null) {
            for (PromptLibrarySource source : librarySources) {
                result.add(new TemplateSourceResponse(
                        source.getId(),
                        source.getName(),
                        source.getUrl(),
                        count(counts, source.getId())));
            }
        }
        return result;
    }

    private int count(Map<String, Integer> counts, String sourceId) {
        Integer count = counts.get(sourceId);
        return count == null ? 0 : count;
    }

    private int countImageRelated() {
        int count = 0;
        for (ImagePromptTemplate template : templates) {
            if (template.isImageRelated()) {
                count++;
            }
        }
        return count;
    }

    private void validate(ImageTemplateQuery query) {
        if (query.getPage() < 1) {
            throw new ImageTemplateQueryValidationException("page 必须大于等于 1");
        }
        if (query.getSize() < 1 || query.getSize() > 100) {
            throw new ImageTemplateQueryValidationException("size 必须在 1 到 100 之间");
        }
    }

    private boolean matchesSource(ImagePromptTemplate template, String normalizedSource) {
        return !hasText(normalizedSource)
                || "all".equals(normalizedSource)
                || normalize(template.getSourceId()).equals(normalizedSource);
    }

    private boolean matchesCategory(ImagePromptTemplate template, String normalizedCategory) {
        if (!hasText(normalizedCategory) || "all".equals(normalizedCategory)) {
            return true;
        }
        return normalize(template.getCategorySlug()).equals(normalizedCategory)
                || normalize(template.getCategory()).equals(normalizedCategory);
    }

    private boolean matchesFunctionCategory(ImagePromptTemplate template,
                                            String normalizedCategory) {
        return !hasText(normalizedCategory)
                || "all".equals(normalizedCategory)
                || normalize(template.getFunctionCategorySlug()).equals(normalizedCategory)
                || normalize(template.getFunctionCategory()).equals(normalizedCategory);
    }

    private boolean matchesFunctionScene(ImagePromptTemplate template,
                                         String normalizedScene) {
        return !hasText(normalizedScene)
                || "all".equals(normalizedScene)
                || normalize(template.getFunctionSceneSlug()).equals(normalizedScene)
                || normalize(template.getFunctionScene()).equals(normalizedScene);
    }

    private boolean matchesKeyword(ImagePromptTemplate template, String normalizedKeyword) {
        if (!hasText(normalizedKeyword)) {
            return true;
        }
        StringBuilder haystack = new StringBuilder();
        haystack.append(template.getTitle()).append(' ')
                .append(template.getSummary()).append(' ')
                .append(template.getCategory()).append(' ')
                .append(template.getSourceName()).append(' ')
                .append(template.getPromptTemplate());
        if (template.getTags() != null) {
            for (String tag : template.getTags()) {
                haystack.append(' ').append(tag);
            }
        }
        return normalize(haystack.toString()).contains(normalizedKeyword);
    }

    private Map<String, Object> resolveTemplate(Map<String, Object> jsonTemplate,
                                                Map<String, Object> variables) {
        Map<String, Object> resolved = new LinkedHashMap<String, Object>();
        if (jsonTemplate == null) {
            return resolved;
        }
        for (Map.Entry<String, Object> entry : jsonTemplate.entrySet()) {
            Object value = entry.getValue();
            if (variables != null && variables.containsKey(entry.getKey())) {
                value = variables.get(entry.getKey());
            }
            resolved.put(entry.getKey(), resolveValue(value, variables));
        }
        return resolved;
    }

    @SuppressWarnings("unchecked")
    private Object resolveValue(Object value, Map<String, Object> variables) {
        if (value instanceof Map) {
            Map<String, Object> valueMap = (Map<String, Object>) value;
            Map<String, Object> resolved = new LinkedHashMap<String, Object>();
            for (Map.Entry<String, Object> entry : valueMap.entrySet()) {
                Object nestedValue = entry.getValue();
                if (variables != null && variables.containsKey(entry.getKey())) {
                    nestedValue = variables.get(entry.getKey());
                }
                resolved.put(entry.getKey(), resolveValue(nestedValue, variables));
            }
            return resolved;
        }
        if (value instanceof List) {
            List<Object> resolved = new ArrayList<Object>();
            for (Object item : (List<Object>) value) {
                resolved.add(resolveValue(item, variables));
            }
            return resolved;
        }
        return value;
    }

    @SuppressWarnings("unchecked")
    private void appendValue(StringBuilder prompt, Object value, int indent) {
        if (value instanceof Map) {
            prompt.append("\n");
            appendMap(prompt, (Map<String, Object>) value, indent + 1);
            return;
        }
        if (value instanceof List) {
            List<Object> values = (List<Object>) value;
            for (Object item : values) {
                prompt.append("\n").append(indent(indent + 1)).append("- ");
                appendValue(prompt, item, indent + 1);
            }
            return;
        }
        prompt.append(value == null ? "" : value.toString());
    }

    private void appendMap(StringBuilder prompt, Map<String, Object> values, int indent) {
        for (Map.Entry<String, Object> entry : values.entrySet()) {
            prompt.append(indent(indent)).append("- ").append(entry.getKey()).append(": ");
            appendValue(prompt, entry.getValue(), indent);
            prompt.append("\n");
        }
    }

    private String indent(int indent) {
        StringBuilder spaces = new StringBuilder();
        for (int i = 0; i < indent; i++) {
            spaces.append("  ");
        }
        return spaces.toString();
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

    private String normalize(String value) {
        return value == null ? "" : value.trim().toLowerCase(Locale.ROOT);
    }

    private boolean hasText(String value) {
        return value != null && !value.trim().isEmpty();
    }
}
