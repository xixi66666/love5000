package com.example.imagetemplate.service;

public class ImagePromptTemplateNotFoundException extends RuntimeException {

    public ImagePromptTemplateNotFoundException(String id) {
        super("Image prompt template not found: " + id);
    }
}
