package com.example.guitar.storage.service;

public interface OssCleanupService {

    void deleteOrEnqueue(String objectKey, String businessType);
}
