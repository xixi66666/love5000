package com.example.guitar.storage.service;

import com.example.guitar.storage.model.OssCleanupTask;

public interface OssCleanupService {

    void deleteOrEnqueue(String objectKey, String businessType);

    void deleteEnqueued(OssCleanupTask task);
}
