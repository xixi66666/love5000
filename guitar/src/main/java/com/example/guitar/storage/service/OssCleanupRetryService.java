package com.example.guitar.storage.service;

import com.example.common.util.OssUtil;
import com.example.guitar.storage.dao.OssCleanupTaskDao;
import com.example.guitar.storage.model.OssCleanupTask;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.time.Clock;
import java.time.LocalDateTime;
import java.util.List;

/** Polls the durable cleanup queue; claims use expected-state updates for MySQL 5.7 compatibility. */
@Service
public class OssCleanupRetryService {
    private static final Logger LOGGER = LoggerFactory.getLogger(OssCleanupRetryService.class);
    private static final int BATCH_SIZE = 50;
    private final OssCleanupTaskDao taskDao;
    private final ObjectProvider<OssUtil> ossProvider;
    private final Clock clock;

    @Autowired
    public OssCleanupRetryService(OssCleanupTaskDao taskDao, ObjectProvider<OssUtil> ossProvider) {
        this(taskDao, ossProvider, Clock.systemDefaultZone());
    }

    public OssCleanupRetryService(OssCleanupTaskDao taskDao, ObjectProvider<OssUtil> ossProvider, Clock clock) {
        this.taskDao = taskDao; this.ossProvider = ossProvider; this.clock = clock;
    }

    @Scheduled(initialDelay = 60000L, fixedDelay = 300000L)
    public void retryDueTasks() {
        LocalDateTime now = LocalDateTime.now(clock);
        taskDao.recoverStaleProcessing(now.minusMinutes(15), now);
        List<OssCleanupTask> tasks = taskDao.findDuePending(now, BATCH_SIZE);
        for (OssCleanupTask task : tasks) retryOne(task, now);
    }

    private void retryOne(OssCleanupTask task, LocalDateTime now) {
        if (task == null || task.getId() == null || taskDao.claimPending(task.getId(), now) != 1) return;
        OssUtil oss = ossProvider.getIfAvailable();
        if (oss == null) { failed(task, now, "OSS unavailable"); return; }
        try {
            oss.delete(task.getObjectKey());
            taskDao.markSuccess(task.getId(), now);
        } catch (RuntimeException failure) {
            LOGGER.warn("OSS cleanup retry failed, taskId={}, objectKey={}", task.getId(), safe(task.getObjectKey()));
            failed(task, now, "OSS cleanup failed");
        }
    }

    private void failed(OssCleanupTask task, LocalDateTime now, String error) {
        int retries = (task.getRetryCount() == null ? 0 : task.getRetryCount()) + 1;
        if (retries >= 5) { taskDao.markFailed(task.getId(), retries, safe(error), now); return; }
        taskDao.reschedule(task.getId(), retries, now.plusMinutes(delayMinutes(retries)), safe(error), now);
    }

    private int delayMinutes(int retryCount) {
        switch (retryCount) { case 1: return 5; case 2: return 30; case 3: return 120; default: return 720; }
    }

    private String safe(String value) {
        if (value == null) return "";
        String result = value.replaceAll("[\\p{Cntrl}]", "?");
        return result.length() > 200 ? result.substring(0, 200) : result;
    }
}
