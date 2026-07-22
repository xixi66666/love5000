package com.example.guitar.storage.service;

import com.example.common.util.OssUtil;
import com.example.guitar.storage.dao.OssCleanupTaskDao;
import com.example.guitar.storage.model.OssCleanupTask;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;

@Service
public class OssCleanupServiceImpl implements OssCleanupService {

    private static final Logger LOGGER = LoggerFactory.getLogger(OssCleanupServiceImpl.class);
    private static final String PENDING = "PENDING";

    private final ObjectProvider<OssUtil> ossUtilProvider;
    private final OssCleanupTaskDao ossCleanupTaskDao;

    public OssCleanupServiceImpl(ObjectProvider<OssUtil> ossUtilProvider, OssCleanupTaskDao ossCleanupTaskDao) {
        this.ossUtilProvider = ossUtilProvider;
        this.ossCleanupTaskDao = ossCleanupTaskDao;
    }

    @Override
    public void deleteOrEnqueue(String objectKey, String businessType) {
        if (objectKey == null || objectKey.trim().isEmpty()) {
            return;
        }
        OssUtil ossUtil = ossUtilProvider.getIfAvailable();
        if (ossUtil == null) {
            enqueue(objectKey, businessType, "OSS unavailable");
            return;
        }
        try {
            ossUtil.delete(objectKey);
        } catch (RuntimeException exception) {
            enqueue(objectKey, businessType, "OSS deletion failed");
        }
    }

    private void enqueue(String objectKey, String businessType, String lastError) {
        OssCleanupTask task = new OssCleanupTask();
        task.setObjectKey(objectKey.trim());
        task.setBusinessType(normalizeBusinessType(businessType));
        task.setStatus(PENDING);
        task.setRetryCount(0);
        task.setNextRetryAt(LocalDateTime.now());
        task.setLastError(lastError);
        if (ossCleanupTaskDao.insertPending(task) != 1) {
            LOGGER.warn("Failed to persist OSS cleanup task");
            throw new IllegalStateException("Failed to persist OSS cleanup task");
        }
    }

    private String normalizeBusinessType(String businessType) {
        return businessType == null || businessType.trim().isEmpty() ? "UNKNOWN" : businessType.trim();
    }
}
