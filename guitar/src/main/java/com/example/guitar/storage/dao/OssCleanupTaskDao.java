package com.example.guitar.storage.dao;

import com.example.guitar.storage.model.OssCleanupTask;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.time.LocalDateTime;
import java.util.List;

@Mapper
public interface OssCleanupTaskDao {

    int insertPending(OssCleanupTask task);

    List<OssCleanupTask> findDuePending(@Param("now") LocalDateTime now, @Param("limit") int limit);

    int claimPending(@Param("id") Long id, @Param("now") LocalDateTime now);

    int recoverStaleProcessing(@Param("cutoff") LocalDateTime cutoff, @Param("now") LocalDateTime now);

    int markSuccess(@Param("id") Long id, @Param("now") LocalDateTime now);

    int reschedule(@Param("id") Long id, @Param("retryCount") int retryCount,
                   @Param("nextRetryAt") LocalDateTime nextRetryAt, @Param("lastError") String lastError,
                   @Param("now") LocalDateTime now);

    int markFailed(@Param("id") Long id, @Param("retryCount") int retryCount,
                   @Param("lastError") String lastError, @Param("now") LocalDateTime now);
}
