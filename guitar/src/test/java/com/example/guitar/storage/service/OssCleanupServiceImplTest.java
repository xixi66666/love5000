package com.example.guitar.storage.service;

import com.example.common.util.OssUtil;
import com.example.guitar.storage.dao.OssCleanupTaskDao;
import com.example.guitar.storage.model.OssCleanupTask;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.ObjectProvider;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
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
        assertThat(task.getLastError()).isEqualTo("OSS deletion failed");
    }

    @Test
    void absentOssEnqueuesKnownObjectInsteadOfDroppingIt() {
        when(ossUtilProvider.getIfAvailable()).thenReturn(null);

        service.deleteOrEnqueue("old/avatar.png", "AVATAR");

        assertThat(capturedTask().getLastError()).isEqualTo("OSS unavailable");
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
