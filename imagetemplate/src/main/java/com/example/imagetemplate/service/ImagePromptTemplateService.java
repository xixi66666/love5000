package com.example.imagetemplate.service;

import com.example.imagetemplate.dto.PromptRenderRequest;
import com.example.imagetemplate.dto.TemplateCategoryResponse;
import com.example.imagetemplate.model.ImagePromptTemplate;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

@Service
public class ImagePromptTemplateService {

    private final List<ImagePromptTemplate> templates;

    public ImagePromptTemplateService(ObjectMapper objectMapper) {
        this.templates = loadTemplates(objectMapper);
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
        Map<String, TemplateCategoryResponse> categories = new LinkedHashMap<String, TemplateCategoryResponse>();
        for (ImagePromptTemplate template : templates) {
            TemplateCategoryResponse category = categories.get(template.getCategorySlug());
            if (category == null) {
                category = new TemplateCategoryResponse(template.getCategory(), template.getCategorySlug(), 0);
                categories.put(template.getCategorySlug(), category);
            }
            category.setCount(category.getCount() + 1);
        }
        return new ArrayList<TemplateCategoryResponse>(categories.values());
    }

    public ImagePromptTemplate findById(String id) {
        for (ImagePromptTemplate template : templates) {
            if (template.getId().equals(id)) {
                return template;
            }
        }
        throw new ImagePromptTemplateNotFoundException(id);
    }

    public String renderPrompt(String id, PromptRenderRequest request) {
        ImagePromptTemplate template = findById(id);
        Map<String, Object> variables = request == null ? null : request.getVariables();
        String extraInstruction = request == null ? null : request.getExtraInstruction();
        Map<String, Object> resolvedTemplate = resolveTemplate(template.getJsonTemplate(), variables);

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

    private List<ImagePromptTemplate> loadTemplates(ObjectMapper objectMapper) {
        try {
            return objectMapper.readValue(
                    new ClassPathResource("templates/image-prompt-templates.json").getInputStream(),
                    new TypeReference<List<ImagePromptTemplate>>() {
                    });
        } catch (IOException e) {
            throw new IllegalStateException("Failed to load image prompt templates", e);
        }
    }

    private boolean matchesCategory(ImagePromptTemplate template, String normalizedCategory) {
        if (!hasText(normalizedCategory) || "all".equals(normalizedCategory)) {
            return true;
        }
        return normalize(template.getCategorySlug()).equals(normalizedCategory)
                || normalize(template.getCategory()).equals(normalizedCategory);
    }

    private boolean matchesKeyword(ImagePromptTemplate template, String normalizedKeyword) {
        if (!hasText(normalizedKeyword)) {
            return true;
        }
        StringBuilder haystack = new StringBuilder();
        haystack.append(template.getTitle()).append(' ')
                .append(template.getSummary()).append(' ')
                .append(template.getCategory()).append(' ')
                .append(template.getPromptTemplate());
        if (template.getTags() != null) {
            for (String tag : template.getTags()) {
                haystack.append(' ').append(tag);
            }
        }
        return normalize(haystack.toString()).contains(normalizedKeyword);
    }

    private Map<String, Object> resolveTemplate(Map<String, Object> jsonTemplate, Map<String, Object> variables) {
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

    private String normalize(String value) {
        return value == null ? "" : value.trim().toLowerCase(Locale.ROOT);
    }

    private boolean hasText(String value) {
        return value != null && !value.trim().isEmpty();
    }
}
