package com.ycxandwuqian.love.controller;

import org.springframework.core.io.Resource;
import org.springframework.core.io.UrlResource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import javax.servlet.http.HttpServletRequest;
import java.io.IOException;
import java.net.MalformedURLException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
@Controller
@RequestMapping("/api/photos")
public class UploadPhotoController {

    private static final String UPLOAD_DIR = "D:/Code/Java_Code/love530/lovestory/src/main/resources/static/images/";


    @PostMapping("/upload")
    @ResponseBody
    public Map<String, Object> uploadPhoto(
            @RequestParam("file") MultipartFile file,
            @RequestParam("category") String category,
            @RequestParam(value = "description", defaultValue = "") String description,
            HttpServletRequest request) {

        Map<String, Object> response = new HashMap<>();

        try {
            if (file.isEmpty()) {
                response.put("success", false);
                response.put("message", "请选择要上传的文件");
                return response;
            }

            String originalFilename = file.getOriginalFilename();
            if (originalFilename == null || !originalFilename.matches(".*\\.(jpg|jpeg|png|gif|webp)$")) {
                response.put("success", false);
                response.put("message", "只支持 jpg、png、gif、webp 格式的图片");
                return response;
            }

            String extension = originalFilename.substring(originalFilename.lastIndexOf("."));
            String newFilename = UUID.randomUUID().toString() + extension;

            String realPath = UPLOAD_DIR;
            System.out.println("上传目录: " + realPath);
            Path uploadPath = Paths.get(realPath);

            if (!Files.exists(uploadPath)) {
                Files.createDirectories(uploadPath);
                System.out.println("创建目录: " + uploadPath.toString());
            }

            Path filePath = uploadPath.resolve(newFilename);
            Files.copy(file.getInputStream(), filePath);

            System.out.println("文件上传成功: " + filePath.toString());

            response.put("success", true);
            response.put("message", "上传成功");
            response.put("filename", newFilename);
            response.put("category", category);
            response.put("description", description);
            response.put("url", "/" + UPLOAD_DIR + "/" + newFilename);

        } catch (IOException e) {
            response.put("success", false);
            response.put("message", "上传失败: " + e.getMessage());
            e.printStackTrace();
        }

        return response;
    }

    @GetMapping("/{filename}")
    @ResponseBody
    public ResponseEntity<Resource> serveFile(@PathVariable String filename, HttpServletRequest request) {
        try {
            String realPath = request.getServletContext().getRealPath("/" + UPLOAD_DIR);
            Path filePath = Paths.get(realPath).resolve(filename).normalize();
            Resource resource = new UrlResource(filePath.toUri());

            if (!resource.exists() || !resource.isReadable()) {
                return ResponseEntity.notFound().build();
            }

            String contentType = Files.probeContentType(filePath);
            if (contentType == null) {
                contentType = "application/octet-stream";
            }

            return ResponseEntity.ok()
                    .contentType(MediaType.parseMediaType(contentType))
                    .header(HttpHeaders.CONTENT_DISPOSITION, "inline; filename=\"" + resource.getFilename() + "\"")
                    .body(resource);

        } catch (MalformedURLException e) {
            return ResponseEntity.badRequest().build();
        } catch (IOException e) {
            return ResponseEntity.internalServerError().build();
        }
    }
}
