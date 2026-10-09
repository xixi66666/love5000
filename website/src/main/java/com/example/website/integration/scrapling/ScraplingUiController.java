package com.example.website.integration.scrapling;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/services/scrapling-ui")
@ConditionalOnProperty(prefix = "scrapling-ui.click-start", name = "enabled", havingValue = "true")
public class ScraplingUiController {

    private final ScraplingUiProcessManager processManager;

    public ScraplingUiController(ScraplingUiProcessManager processManager) {
        this.processManager = processManager;
    }

    @PostMapping("/start")
    public ResponseEntity<Object> start() {
        try {
            ScraplingUiStartResult result = processManager.start();
            Map<String, Object> body = new HashMap<String, Object>();
            body.put("success", true);
            body.put("status", result.getStatus());
            body.put("url", result.getUrl());
            return ResponseEntity.ok(body);
        } catch (ScraplingUiStartException exception) {
            Map<String, Object> error = new HashMap<String, Object>();
            error.put("success", false);
            error.put("message", exception.getMessage());
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(error);
        }
    }

    @GetMapping("/status")
    public Map<String, Object> status() {
        Map<String, Object> body = new HashMap<String, Object>();
        body.put("success", true);
        body.put("running", processManager.isRunning());
        body.put("url", processManager.appUrl());
        return body;
    }
}
