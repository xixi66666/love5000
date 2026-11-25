package com.ycxandwuqian.love.controller;

import com.example.common.util.OssUtil;
import com.ycxandwuqian.love.dao.PhotoDao;
import com.ycxandwuqian.love.service.PhotoService;
import com.ycxandwuqian.love.service.PhotoServiceImpl;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Autowired;
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
@RequestMapping("/api/photos")
public class UploadPhotoController {

    private final PhotoService photoService;

    @Autowired
    public UploadPhotoController(ObjectProvider<OssUtil> ossUtilProvider,
                                 PhotoDao photoDao,
                                 ObjectProvider<PhotoService> photoServiceProvider) {
        PhotoService availableService = photoServiceProvider.getIfAvailable();
        this.photoService = availableService != null
                ? availableService
                : new PhotoServiceImpl(ossUtilProvider, photoDao);
    }

    /**
     * 保留原构造签名，便于在 Spring MVC 切片或直接实例化时复用同一套照片业务。
     */
    public UploadPhotoController(ObjectProvider<OssUtil> ossUtilProvider, PhotoDao photoDao) {
        this.photoService = new PhotoServiceImpl(ossUtilProvider, photoDao);
    }

    @PostMapping("/upload")
    public Map<String, Object> uploadPhoto(@RequestParam("file") MultipartFile file,
                                           @RequestParam("category") String category,
                                           @RequestParam(value = "description", defaultValue = "") String description) {
        return photoService.uploadPhoto(file, category, description);
    }

    @GetMapping
    public Map<String, Object> listPhotos() {
        return photoService.listPhotos();
    }

    @DeleteMapping("/{id}")
    public Map<String, Object> deletePhoto(@PathVariable("id") Long id) {
        return photoService.deletePhoto(id);
    }
}
