package com.example.guitar.storage.service;

import com.example.common.util.OssUtil;
import com.example.guitar.storage.dao.OssCleanupTaskDao;
import com.example.guitar.storage.model.OssCleanupTask;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.ObjectProvider;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class OssCleanupServiceImplTest {

    private ObjectProvider<OssUtil> ossUtilProvider;
    private OssCleanupTaskDao cleanupTaskDao;
    private OssCleanupServiceImpl service;

    @BeforeEach
    void setUp() {
        ossUtilProvider = ossUtilProvider();
        cleanupTaskDao = mock(OssCleanupTaskDao.class);
        when(cleanupTaskDao.insertPending(any())).thenReturn(1);
        service = new OssCleanupServiceImpl(ossUtilProvider, cleanupTaskDao);
    }

    @Test
    void blankObjectKeyIsIgnored() {
        service.deleteOrEnqueue("  ", "AVATAR");

        verify(cleanupTaskDao, never()).insertPending(any());
    }

    @Test
    void deletionFailureCreatesPendingCleanupTask() {
        OssUtil ossUtil = mock(OssUtil.class);
        when(ossUtilProvider.getIfAvailable()).thenReturn(ossUtil);
        org.mockito.Mockito.doThrow(new IllegalStateException("private key"))
                .when(ossUtil).delete("old/avatar.png");

        service.deleteOrEnqueue("old/avatar.png", "AVATAR");

        OssCleanupTask task = capturedTask();
        assertThat(task.getObjectKey()).isEqualTo("old/avatar.png");
        assertThat(task.getBusinessType()).isEqualTo("AVATAR");
        assertThat(task.getStatus()).isEqualTo("PENDING");
        assertThat(task.getRetryCount()).isZero();
        assertThat(task.getNextRetryAt()).isNotNull();
        assertThat(task.getLastError()).contains("OSS deletion failed", "IllegalStateException")
                .doesNotContain("private key");
    }

    @Test
    void absentOssEnqueuesKnownObjectInsteadOfDroppingIt() {
        when(ossUtilProvider.getIfAvailable()).thenReturn(null);

        service.deleteOrEnqueue("old/avatar.png", "AVATAR");

        assertThat(capturedTask().getLastError()).isEqualTo("OSS unavailable");
    }

    @Test
    void existingOutboxTaskIsClaimedAndMarkedSuccessWithoutAnotherInsert() {
        OssUtil ossUtil = mock(OssUtil.class);
        when(ossUtilProvider.getIfAvailable()).thenReturn(ossUtil);
        when(cleanupTaskDao.claimPending(eq(9L), eq(0L), any())).thenReturn(1);
        when(cleanupTaskDao.markSuccess(eq(9L), eq(1L), any())).thenReturn(1);
        OssCleanupTask task = new OssCleanupTask();
        task.setId(9L); task.setObjectKey("old/sheet.pdf"); task.setClaimVersion(0L); task.setRetryCount(0);

        service.deleteEnqueued(task);

        verify(ossUtil).delete("old/sheet.pdf");
        verify(cleanupTaskDao).markSuccess(eq(9L), eq(1L), any());
        verify(cleanupTaskDao, never()).insertPending(any());
    }

    @Test
    void persistenceFailureIsSurfacedInsteadOfSilentlyDroppingCleanupWork() {
        when(cleanupTaskDao.insertPending(any())).thenReturn(0);

        assertThatThrownBy(() -> service.deleteOrEnqueue("old/avatar.png", "AVATAR"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessage("Failed to persist OSS cleanup task");
    }

    @Test
    void deleteAndEnqueueFailurePreservesDeleteFailureAsSuppressedCause() {
        OssUtil ossUtil = mock(OssUtil.class);
        when(ossUtilProvider.getIfAvailable()).thenReturn(ossUtil);
        IllegalStateException deleteFailure = new IllegalStateException("delete failed");
        org.mockito.Mockito.doThrow(deleteFailure).when(ossUtil).delete("old/avatar.png");
        when(cleanupTaskDao.insertPending(any())).thenReturn(0);

        IllegalStateException failure = (IllegalStateException) org.assertj.core.api.Assertions.catchThrowable(
                () -> service.deleteOrEnqueue("old/avatar.png", "AVATAR"));

        assertThat(failure).hasMessage("Failed to persist OSS cleanup task");
        assertThat(failure.getSuppressed()).contains(deleteFailure);
    }

    @Test
    void daoInsertFailureIsSurfacedWithTheOriginalFailureAttached() {
        OssUtil ossUtil = mock(OssUtil.class);
        when(ossUtilProvider.getIfAvailable()).thenReturn(ossUtil);
        IllegalStateException deleteFailure = new IllegalStateException("delete failed");
        IllegalStateException insertFailure = new IllegalStateException("insert failed");
        org.mockito.Mockito.doThrow(deleteFailure).when(ossUtil).delete("old/avatar.png");
        when(cleanupTaskDao.insertPending(any())).thenThrow(insertFailure);

        IllegalStateException failure = (IllegalStateException) org.assertj.core.api.Assertions.catchThrowable(
                () -> service.deleteOrEnqueue("old/avatar.png", "AVATAR"));

        assertThat(failure).isSameAs(insertFailure);
        assertThat(failure.getSuppressed()).contains(deleteFailure);
    }

    private OssCleanupTask capturedTask() {
        ArgumentCaptor<OssCleanupTask> captor = ArgumentCaptor.forClass(OssCleanupTask.class);
        verify(cleanupTaskDao).insertPending(captor.capture());
        return captor.getValue();
    }

    @SuppressWarnings("unchecked")
    private ObjectProvider<OssUtil> ossUtilProvider() {
        return (ObjectProvider<OssUtil>) mock(ObjectProvider.class);
    }
}
