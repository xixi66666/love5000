package com.example.website.prompt.library.controller;

import com.example.website.prompt.library.dto.PromptCreateRequest;
import com.example.website.prompt.library.dto.PromptCreateResponse;
import com.example.website.prompt.library.dto.PromptDetailResponse;
import com.example.website.prompt.library.dto.PromptListResponse;
import com.example.website.prompt.library.dto.PromptMetaResponse;
import com.example.website.prompt.library.dto.PromptSearchRequest;
import com.example.website.prompt.library.service.PromptLibraryService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/prompts")
public class PromptLibraryController {

    private final PromptLibraryService service;

    public PromptLibraryController(PromptLibraryService service) {
        this.service = service;
    }

    @GetMapping("/meta")
    public PromptMetaResponse meta() {
        return service.meta();
    }

    @GetMapping
    public PromptListResponse list(PromptSearchRequest request) {
        return service.search(request);
    }

    @GetMapping("/{id}")
    public ResponseEntity<Object> detail(@PathVariable Long id) {
        PromptDetailResponse detail = service.detail(id);
        if (detail == null) {
            Map<String, Object> error = new HashMap<String, Object>();
            error.put("success", false);
            error.put("message", "提示词不存在");
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(error);
        }
        return ResponseEntity.ok(detail);
    }

    @PostMapping
    public ResponseEntity<Object> create(@RequestBody PromptCreateRequest request) {
        try {
            PromptCreateResponse response = service.create(request);
            return ResponseEntity.ok(response);
        } catch (IllegalArgumentException exception) {
            Map<String, Object> error = new HashMap<String, Object>();
            error.put("success", false);
            error.put("message", exception.getMessage());
            return ResponseEntity.badRequest().body(error);
        }
    }
}