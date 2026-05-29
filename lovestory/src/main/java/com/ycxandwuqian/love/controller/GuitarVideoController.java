package com.ycxandwuqian.love.controller;

import com.ycxandwuqian.love.service.GuitarVideoService;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.util.Map;

@RestController
@RequestMapping("/api/guitar-videos")
public class GuitarVideoController {

    private final GuitarVideoService guitarVideoService;

    public GuitarVideoController(GuitarVideoService guitarVideoService) {
        this.guitarVideoService = guitarVideoService;
    }

    @GetMapping
    public Map<String, Object> listVideos() {
        return guitarVideoService.listVideos();
    }

    @PostMapping("/upload")
    public Map<String, Object> uploadVideo(@RequestParam("file") MultipartFile file,
                                           @RequestParam(value = "cover", required = false) MultipartFile cover,
                                           @RequestParam("title") String title,
                                           @RequestParam(value = "description", defaultValue = "") String description,
                                           @RequestParam(value = "tag", defaultValue = "") String tag,
                                           @RequestParam(value = "sortOrder", required = false) Integer sortOrder) {
        return guitarVideoService.uploadVideo(file, cover, title, description, tag, sortOrder);
    }

    @PostMapping("/{id}/cover")
    public Map<String, Object> uploadCover(@PathVariable("id") Long id,
                                           @RequestParam("cover") MultipartFile cover) {
        return guitarVideoService.uploadCover(id, cover);
    }

    @DeleteMapping("/{id}")
    public Map<String, Object> deleteVideo(@PathVariable("id") Long id) {
        return guitarVideoService.deleteVideo(id);
    }
}
