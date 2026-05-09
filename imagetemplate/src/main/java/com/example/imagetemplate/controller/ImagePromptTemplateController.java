package com.example.imagetemplate.controller;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.example.imagetemplate.dto.PromptRenderRequest;
import com.example.imagetemplate.dto.PromptRenderResponse;
import com.example.imagetemplate.dto.ImageGenerationRequest;
import com.example.imagetemplate.dto.ImageGenerationResponse;
import com.example.imagetemplate.dto.ReferenceImageInput;
import com.example.imagetemplate.dto.TemplateCategoryResponse;
import com.example.imagetemplate.model.ImagePromptTemplate;
import com.example.imagetemplate.service.ImageGenerationException;
import com.example.imagetemplate.service.ImagePromptTemplateNotFoundException;
import com.example.imagetemplate.service.ImagePromptTemplateService;
import com.example.imagetemplate.service.OpenAiImageGenerationService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/image-templates")
public class ImagePromptTemplateController {

    private static final Logger LOGGER = LoggerFactory.getLogger(ImagePromptTemplateController.class);

    private final ImagePromptTemplateService imagePromptTemplateService;

    private final OpenAiImageGenerationService openAiImageGenerationService;

    private final ObjectMapper objectMapper;

    public ImagePromptTemplateController(ImagePromptTemplateService imagePromptTemplateService,
                                         OpenAiImageGenerationService openAiImageGenerationService,
                                         ObjectMapper objectMapper) {
        this.imagePromptTemplateService = imagePromptTemplateService;
        this.openAiImageGenerationService = openAiImageGenerationService;
        this.objectMapper = objectMapper;
    }

    @GetMapping
    public Map<String, Object> listTemplates(@RequestParam(value = "category", required = false) String category,
                                             @RequestParam(value = "keyword", required = false) String keyword) {
        List<ImagePromptTemplate> templates = imagePromptTemplateService.listTemplates(category, keyword);
        Map<String, Object> result = new HashMap<String, Object>();
        result.put("success", true);
        result.put("templates", templates);
        result.put("total", templates.size());
        return result;
    }

    @GetMapping("/categories")
    public Map<String, Object> listCategories() {
        List<TemplateCategoryResponse> categories = imagePromptTemplateService.listCategories();
        Map<String, Object> result = new HashMap<String, Object>();
        result.put("success", true);
        result.put("categories", categories);
        return result;
    }

    @GetMapping("/{id}")
    public Map<String, Object> getTemplate(@PathVariable("id") String id) {
        Map<String, Object> result = new HashMap<String, Object>();
        result.put("success", true);
        result.put("template", imagePromptTemplateService.findById(id));
        return result;
    }

    @PostMapping("/{id}/prompt")
    public PromptRenderResponse renderPrompt(@PathVariable("id") String id,
                                             @RequestBody(required = false) PromptRenderRequest request) {
        return new PromptRenderResponse(true, id, imagePromptTemplateService.renderPrompt(id, request));
    }

    @PostMapping(value = "/{id}/generate", consumes = MediaType.APPLICATION_JSON_VALUE)
    public ImageGenerationResponse generateImage(@PathVariable("id") String id,
                                                 @RequestHeader(value = "X-OpenAI-Api-Key", required = false) String userApiKey,
                                                 @RequestBody(required = false) ImageGenerationRequest request) {
        return openAiImageGenerationService.generate(id, request, userApiKey);
    }

    @PostMapping(value = "/{id}/generate", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ImageGenerationResponse generateImageWithReferences(@PathVariable("id") String id,
                                                               @RequestHeader(value = "X-OpenAI-Api-Key", required = false) String userApiKey,
                                                               @RequestParam(value = "variables", required = false) String variables,
                                                               @RequestParam(value = "extraInstruction", required = false) String extraInstruction,
                                                               @RequestParam(value = "prompt", required = false) String prompt,
                                                               @RequestParam(value = "size", required = false) String size,
                                                               @RequestParam(value = "quality", required = false) String quality,
                                                               @RequestParam(value = "outputFormat", required = false) String outputFormat,
                                                               @RequestParam(value = "background", required = false) String background,
                                                               @RequestParam(value = "referenceImages", required = false) MultipartFile[] referenceImages) {
        ImageGenerationRequest request = new ImageGenerationRequest();
        request.setVariables(readVariables(variables));
        request.setExtraInstruction(extraInstruction);
        request.setPrompt(prompt);
        request.setSize(size);
        request.setQuality(quality);
        request.setOutputFormat(outputFormat);
        request.setBackground(background);
        request.setReferenceImages(readReferenceImages(referenceImages));
        return openAiImageGenerationService.generate(id, request, userApiKey);
    }

    private Map<String, Object> readVariables(String variables) {
        if (variables == null || variables.trim().isEmpty()) {
            return new LinkedHashMap<String, Object>();
        }
        try {
            return objectMapper.readValue(variables, new TypeReference<Map<String, Object>>() {
            });
        } catch (IOException exception) {
            throw new ImageGenerationException("Variables must be valid JSON.", exception);
        }
    }

    private List<ReferenceImageInput> readReferenceImages(MultipartFile[] files) {
        List<ReferenceImageInput> images = new ArrayList<ReferenceImageInput>();
        if (files == null) {
            return images;
        }
        for (MultipartFile file : files) {
            if (file == null || file.isEmpty()) {
                continue;
            }
            try {
                images.add(new ReferenceImageInput(file.getOriginalFilename(), file.getContentType(), file.getBytes()));
            } catch (IOException exception) {
                throw new ImageGenerationException("Failed to read reference image: " + file.getOriginalFilename(), exception);
            }
        }
        return images;
    }

    @ExceptionHandler(ImagePromptTemplateNotFoundException.class)
    @ResponseStatus(HttpStatus.NOT_FOUND)
    public Map<String, Object> handleNotFound(ImagePromptTemplateNotFoundException exception) {
        Map<String, Object> result = new HashMap<String, Object>();
        result.put("success", false);
        result.put("message", exception.getMessage());
        return result;
    }

    @ExceptionHandler(ImageGenerationException.class)
    @ResponseStatus(HttpStatus.BAD_GATEWAY)
    public Map<String, Object> handleGenerationError(ImageGenerationException exception) {
        LOGGER.error("Image generation request failed. message={}", exception.getMessage(), exception);
        Map<String, Object> result = new HashMap<String, Object>();
        result.put("success", false);
        result.put("message", exception.getMessage());
        return result;
    }
}
