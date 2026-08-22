package com.example.guitar.storage.service;

import com.example.common.util.OssUtil;
import com.example.guitar.storage.dao.OssCleanupTaskDao;
import com.example.guitar.storage.model.OssCleanupTask;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.ObjectProvider;

import java.time.Clock;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.Arrays;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class OssCleanupRetryServiceTest {
    private OssCleanupTaskDao dao;
    private ObjectProvider<OssUtil> ossProvider;
    private OssCleanupRetryService service;

    @BeforeEach
    void setUp() {
        dao = mock(OssCleanupTaskDao.class); ossProvider = ossProvider();
        service = new OssCleanupRetryService(dao, ossProvider,
                Clock.fixed(Instant.parse("2026-07-22T02:00:00Z"), ZoneOffset.UTC));
    }

    @Test
    void duePollClaimsEachPendingTaskBeforeDeletingAndContinuesAfterFailure() {
        OssCleanupTask failed = task(1L, "failed-key", 0); OssCleanupTask success = task(2L, "success-key", 0);
        when(dao.findDuePending(any(), anyInt())).thenReturn(Arrays.asList(failed, success));
        when(dao.claimPending(eq(1L), eq(0L), any())).thenReturn(1);
        when(dao.claimPending(eq(2L), eq(0L), any())).thenReturn(1);
        when(dao.markSuccess(eq(2L), eq(1L), any())).thenReturn(1);
        when(dao.reschedule(eq(1L), eq(1L), eq(1), any(), anyString(), any())).thenReturn(1);
        OssUtil oss = mock(OssUtil.class); when(ossProvider.getIfAvailable()).thenReturn(oss);
        doThrow(new IllegalStateException("secret\ntrace")).when(oss).delete("failed-key");

        service.retryDueTasks();

        verify(dao).markSuccess(eq(2L), eq(1L), any());
        ArgumentCaptor<String> error = ArgumentCaptor.forClass(String.class);
        verify(dao).reschedule(eq(1L), eq(1L), eq(1), any(), error.capture(), any());
        assertThat(error.getValue()).doesNotContain("secret").doesNotContain("\n");
    }

    @Test
    void failureBackoffAndFifthFailureArePersisted() {
        OssCleanupTask one = task(1L, "one", 0); OssCleanupTask five = task(5L, "five", 4);
        when(dao.findDuePending(any(), anyInt())).thenReturn(Arrays.asList(one, five));
        when(dao.claimPending(anyLong(), eq(0L), any())).thenReturn(1);
        when(dao.reschedule(eq(1L), eq(1L), eq(1), any(), anyString(), any())).thenReturn(1);
        when(dao.markFailed(eq(5L), eq(1L), eq(5), anyString(), any())).thenReturn(1);
        OssUtil oss = mock(OssUtil.class); when(ossProvider.getIfAvailable()).thenReturn(oss);
        doThrow(new RuntimeException("x")).when(oss).delete(anyString());

        service.retryDueTasks();

        verify(dao).reschedule(eq(1L), eq(1L), eq(1),
                org.mockito.ArgumentMatchers.eq(LocalDateTime.of(2026, 7, 22, 2, 5)), anyString(), any());
        verify(dao).markFailed(eq(5L), eq(1L), eq(5), anyString(), any());
    }

    @Test
    void absentOssReschedulesClaimedTaskAndStaleProcessingIsRecovered() {
        when(dao.recoverStaleProcessing(any(), any())).thenReturn(3);
        when(dao.findDuePending(any(), anyInt())).thenReturn(Arrays.asList(task(9L, "key", 1)));
        when(dao.claimPending(eq(9L), eq(0L), any())).thenReturn(1);
        when(dao.reschedule(eq(9L), eq(1L), eq(2), any(), anyString(), any())).thenReturn(1);
        when(ossProvider.getIfAvailable()).thenReturn(null);

        service.retryDueTasks();

        verify(dao).recoverStaleProcessing(any(), any());
        verify(dao).reschedule(eq(9L), eq(1L), eq(2),
                org.mockito.ArgumentMatchers.eq(LocalDateTime.of(2026, 7, 22, 2, 30)), anyString(), any());
    }

    private OssCleanupTask task(long id, String key, int retries) {
        OssCleanupTask t = new OssCleanupTask(); t.setId(id); t.setObjectKey(key); t.setRetryCount(retries);
        t.setClaimVersion(0L); return t;
    }
    @SuppressWarnings("unchecked") private ObjectProvider<OssUtil> ossProvider() { return (ObjectProvider<OssUtil>) mock(ObjectProvider.class); }
}
