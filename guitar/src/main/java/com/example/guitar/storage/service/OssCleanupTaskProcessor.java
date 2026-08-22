package com.example.guitar.storage.service;

import com.example.common.util.OssUtil;
import com.example.guitar.storage.dao.OssCleanupTaskDao;
import com.example.guitar.storage.model.OssCleanupTask;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;

import java.time.Clock;
import java.time.LocalDateTime;

/** Executes one durable cleanup task with lease-generation fencing. */
final class OssCleanupTaskProcessor {
    private static final Logger LOGGER = LoggerFactory.getLogger(OssCleanupTaskProcessor.class);
    private final OssCleanupTaskDao taskDao;
    private final ObjectProvider<OssUtil> ossProvider;
    private final Clock clock;

    OssCleanupTaskProcessor(OssCleanupTaskDao taskDao, ObjectProvider<OssUtil> ossProvider, Clock clock) {
        this.taskDao = taskDao;
        this.ossProvider = ossProvider;
        this.clock = clock;
    }

    void process(OssCleanupTask task) {
        if (task == null || task.getId() == null) return;
        LocalDateTime now = LocalDateTime.now(clock);
        long expectedVersion = task.getClaimVersion() == null ? 0L : task.getClaimVersion();
        if (taskDao.claimPending(task.getId(), expectedVersion, now) != 1) return;
        long claimVersion = expectedVersion + 1L;
        OssUtil oss = ossProvider.getIfAvailable();
        if (oss == null) {
            failed(task, claimVersion, now, "OSS unavailable");
            return;
        }
        try {
            oss.delete(task.getObjectKey());
            checkLease(taskDao.markSuccess(task.getId(), claimVersion, now), task, claimVersion, "mark success");
        } catch (RuntimeException failure) {
            LOGGER.warn("OSS cleanup failed, taskId={}, objectKey={}", task.getId(), safe(task.getObjectKey()), failure);
            failed(task, claimVersion, now, diagnostic("OSS cleanup failed", failure));
        }
    }

    private void failed(OssCleanupTask task, long claimVersion, LocalDateTime now, String error) {
        int retries = (task.getRetryCount() == null ? 0 : task.getRetryCount()) + 1;
        int affected;
        if (retries >= 5) {
            affected = taskDao.markFailed(task.getId(), claimVersion, retries, safe(error), now);
        } else {
            affected = taskDao.reschedule(task.getId(), claimVersion, retries,
                    now.plusMinutes(delayMinutes(retries)), safe(error), now);
        }
        checkLease(affected, task, claimVersion, "record failure");
    }

    private void checkLease(int affected, OssCleanupTask task, long claimVersion, String operation) {
        if (affected != 1) {
            LOGGER.info("Ignored stale OSS cleanup worker while attempting to {}, taskId={}, claimVersion={}",
                    operation, task.getId(), claimVersion);
        }
    }

    private int delayMinutes(int retryCount) {
        switch (retryCount) { case 1: return 5; case 2: return 30; case 3: return 120; default: return 720; }
    }

    private String diagnostic(String summary, Throwable failure) {
        String type = failure == null ? "" : failure.getClass().getSimpleName();
        return safe(type.isEmpty() ? summary : summary + " (" + type + ")");
    }

    private String safe(String value) {
        if (value == null) return "";
        String result = value.replaceAll("[\\p{Cntrl}]", "?");
        return result.length() > 500 ? result.substring(0, 500) : result;
    }
}
