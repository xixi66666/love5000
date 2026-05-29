package com.ycxandwuqian.love.service;

import org.springframework.web.multipart.MultipartFile;

import java.util.Map;

public interface GuitarVideoService {

    Map<String, Object> listVideos();

    Map<String, Object> uploadVideo(MultipartFile file, MultipartFile cover, String title,
                                    String description, String tag, Integer sortOrder);

    Map<String, Object> uploadCover(Long id, MultipartFile cover);

    Map<String, Object> deleteVideo(Long id);
}
