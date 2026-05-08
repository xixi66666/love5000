package com.example.imagetemplate.controller;

import com.example.imagetemplate.dto.PromptRenderRequest;
import com.example.imagetemplate.dto.PromptRenderResponse;
import com.example.imagetemplate.dto.ImageGenerationRequest;
import com.example.imagetemplate.dto.ImageGenerationResponse;
import com.example.imagetemplate.dto.TemplateCategoryResponse;
import com.example.imagetemplate.model.ImagePromptTemplate;
import com.example.imagetemplate.service.ImageGenerationException;
import com.example.imagetemplate.service.ImagePromptTemplateNotFoundException;
import com.example.imagetemplate.service.ImagePromptTemplateService;
import com.example.imagetemplate.service.OpenAiImageGenerationService;
import org.springframework.http.HttpStatus;
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

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/image-templates")
public class ImagePromptTemplateController {

    private final ImagePromptTemplateService imagePromptTemplateService;

    private final OpenAiImageGenerationService openAiImageGenerationService;

    public ImagePromptTemplateController(ImagePromptTemplateService imagePromptTemplateService,
                                         OpenAiImageGenerationService openAiImageGenerationService) {
        this.imagePromptTemplateService = imagePromptTemplateService;
        this.openAiImageGenerationService = openAiImageGenerationService;
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

    @PostMapping("/{id}/generate")
    public ImageGenerationResponse generateImage(@PathVariable("id") String id,
                                                 @RequestHeader(value = "X-OpenAI-Api-Key", required = false) String userApiKey,
                                                 @RequestBody(required = false) ImageGenerationRequest request) {
        return openAiImageGenerationService.generate(id, request, userApiKey);
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
        Map<String, Object> result = new HashMap<String, Object>();
        result.put("success", false);
        result.put("message", exception.getMessage());
        return result;
    }
}
