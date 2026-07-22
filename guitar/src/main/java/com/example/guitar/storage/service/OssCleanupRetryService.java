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
    private final Clock clock;
    private final OssCleanupTaskProcessor processor;

    @Autowired
    public OssCleanupRetryService(OssCleanupTaskDao taskDao, ObjectProvider<OssUtil> ossProvider) {
        this(taskDao, ossProvider, Clock.systemDefaultZone());
    }

    public OssCleanupRetryService(OssCleanupTaskDao taskDao, ObjectProvider<OssUtil> ossProvider, Clock clock) {
        this.taskDao = taskDao;
        this.clock = clock;
        this.processor = new OssCleanupTaskProcessor(taskDao, ossProvider, clock);
    }

    @Scheduled(initialDelay = 60000L, fixedDelay = 300000L)
    public void retryDueTasks() {
        LocalDateTime now = LocalDateTime.now(clock);
        taskDao.recoverStaleProcessing(now.minusMinutes(15), now);
        List<OssCleanupTask> tasks = taskDao.findDuePending(now, BATCH_SIZE);
        for (OssCleanupTask task : tasks) {
            try {
                processor.process(task);
            } catch (RuntimeException failure) {
                LOGGER.warn("OSS cleanup task processing aborted, taskId={}", task == null ? null : task.getId(), failure);
            }
        }
    }
}
