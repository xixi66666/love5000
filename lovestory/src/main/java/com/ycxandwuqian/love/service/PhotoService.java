package com.ycxandwuqian.love.service;

import org.springframework.web.multipart.MultipartFile;

import java.util.Map;

/**
 * 照片墙业务：上传、列表和删除。
 */
public interface PhotoService {

    Map<String, Object> uploadPhoto(MultipartFile file, String category, String description);

    Map<String, Object> listPhotos();

    Map<String, Object> deletePhoto(Long id);
}
