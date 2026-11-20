package com.example.personalagent.controller;

import com.example.personalagent.service.LocalDocuments;
import org.springframework.core.io.FileSystemResource;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.nio.file.Path;
import java.util.Map;

import static com.example.personalagent.Api.*;

@RestController
@RequestMapping("/api/documents")
public class DocumentController {
    private final LocalDocuments documents;

    public DocumentController(LocalDocuments documents) {
        this.documents = documents;
    }

    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public Object save(@RequestParam MultipartFile file, @RequestParam Map<String,String> fields) throws Exception {
        return ok(map("path", documents.archive(file, fields).path));
    }

    @GetMapping("/original")
    public ResponseEntity<FileSystemResource> original(@RequestParam String path) throws Exception {
        Path original = documents.original(path);
        return ResponseEntity.ok().contentType(MediaType.APPLICATION_OCTET_STREAM)
            .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + original.getFileName() + "\"")
            .body(new FileSystemResource(original));
    }
}
