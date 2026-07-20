package com.example.website.prompt.controller;

import com.example.website.prompt.dto.PromptComposeRequest;
import com.example.website.prompt.dto.PromptSourceRefreshRequest;
import com.example.website.prompt.model.PromptVariant;
import com.example.website.prompt.service.PromptComposeService;
import com.example.website.prompt.service.PromptSourceFetchService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api")
public class PromptConsoleController {

    private final PromptSourceFetchService fetchService;
    private final PromptComposeService composeService;

    public PromptConsoleController(PromptSourceFetchService fetchService, PromptComposeService composeService) {
        this.fetchService = fetchService;
        this.composeService = composeService;
    }

    @GetMapping("/prompt-sources")
    public Map<String, Object> listSources() {
        Map<String, Object> response = new HashMap<String, Object>();
        response.put("success", true);
        response.put("sources", fetchService.listSnapshots());
        return response;
    }

    @PostMapping("/prompt-sources/refresh")
    public Map<String, Object> refreshSources(@RequestBody(required = false) PromptSourceRefreshRequest request) {
        Map<String, Object> response = new HashMap<String, Object>();
        response.put("success", true);
        response.put("sources", fetchService.refresh(request == null ? null : request.getSourceIds()));
        return response;
    }

    @PostMapping("/prompts/compose")
    public Map<String, Object> compose(@RequestBody PromptComposeRequest request) {
        Map<String, Object> response = new HashMap<String, Object>();
        try {
            List<PromptVariant> variants = composeService.compose(request);
            response.put("success", true);
            response.put("results", variants);
            return response;
        } catch (IllegalArgumentException exception) {
            response.put("success", false);
            response.put("message", exception.getMessage());
            return response;
        }
    }
}
