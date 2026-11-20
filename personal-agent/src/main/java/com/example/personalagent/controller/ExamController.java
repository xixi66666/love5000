package com.example.personalagent.controller;

import com.example.personalagent.service.HealthArchive;
import org.springframework.core.io.FileSystemResource;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import java.nio.file.Path;
import java.util.Map;
import static com.example.personalagent.Api.ok;

@RestController
@RequestMapping("/api/exams")
public class ExamController {
    private final HealthArchive archive;
    public ExamController(HealthArchive archive) { this.archive = archive; }

    @GetMapping public Object list() throws Exception { return ok(archive.overview()); }
    @GetMapping("/{id}") public Object detail(@PathVariable String id) throws Exception { return ok(archive.detail(id)); }
    @PostMapping(consumes=MediaType.MULTIPART_FORM_DATA_VALUE)
    public Object save(@RequestParam MultipartFile file, @RequestParam Map<String,String> fields) throws Exception {
        return ok(archive.archive(file, fields));
    }
    @PostMapping("/{id}/analysis") public Object analyze(@PathVariable String id, @RequestBody Map<String,Object> request) throws Exception {
        return ok(archive.analyze(id,request));
    }
    @GetMapping("/{id}/original") public ResponseEntity<FileSystemResource> original(@PathVariable String id) throws Exception {
        Path original = archive.original(id);
        return ResponseEntity.ok().contentType(MediaType.APPLICATION_OCTET_STREAM)
            .header(HttpHeaders.CONTENT_DISPOSITION,"attachment; filename=\"exam-" + original.getFileName() + "\"")
            .body(new FileSystemResource(original));
    }
}
