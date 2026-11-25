package com.ycxandwuqian.love.service;

import com.example.common.util.OssUploadResult;
import com.example.common.util.OssUtil;
import com.ycxandwuqian.love.dao.PhotoDao;
import com.ycxandwuqian.love.model.PhotoRecord;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.mockito.InOrder;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.web.multipart.MultipartFile;

import java.time.LocalDateTime;
import java.util.Arrays;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class PhotoServiceImplTests {

    @Test
    void uploadPhotoShouldUsePredeclaredObjectKeyAndPersistRecord() {
        PhotoDao photoDao = mock(PhotoDao.class);
        OssUtil ossUtil = mock(OssUtil.class);
        ObjectProvider<OssUtil> ossUtilProvider = provider(ossUtil);
        when(ossUtil.uploadWithObjectKey(any(MultipartFile.class), anyString(), anyString()))
                .thenAnswer(invocation -> uploadResult(
                        invocation.getArgument(1), "https://cdn.example/photo.jpg"));
        when(photoDao.insert(any(PhotoRecord.class))).thenAnswer(invocation -> {
            PhotoRecord record = invocation.getArgument(0);
            record.setId(42L);
            return 1;
        });

        MockMultipartFile file = new MockMultipartFile(
                "file", "My Photo.JPG", "image/jpeg", "photo".getBytes());
        PhotoService service = new PhotoServiceImpl(ossUtilProvider, photoDao);

        Map<String, Object> response = service.uploadPhoto(file, " cat ", "  Memory  ");

        assertEquals(Boolean.TRUE, response.get("success"));
        assertEquals("Upload succeeded", response.get("message"));
        assertEquals("https://cdn.example/photo.jpg", response.get("url"));

        Map<?, ?> photo = (Map<?, ?>) response.get("photo");
        assertEquals(42L, photo.get("id"));
        assertEquals("cat", photo.get("category"));
        assertEquals("Memory", photo.get("description"));

        ArgumentCaptor<String> keyCaptor = ArgumentCaptor.forClass(String.class);
        verify(ossUtil).uploadWithObjectKey(
                any(MultipartFile.class), keyCaptor.capture(), eq("image/jpeg"));
        String objectKey = keyCaptor.getValue();
        assertTrue(objectKey.matches(
                "love530/lovestory/photos/cat/\\d{4}/\\d{2}/\\d{2}/[0-9a-f-]{36}\\.jpg"));

        ArgumentCaptor<PhotoRecord> recordCaptor = ArgumentCaptor.forClass(PhotoRecord.class);
        verify(photoDao).insert(recordCaptor.capture());
        assertEquals(objectKey, recordCaptor.getValue().getPath());
        assertEquals("cat", recordCaptor.getValue().getType());
        verify(ossUtil, never()).delete(anyString());
    }

    @Test
    void uploadPhotoShouldCompensateOrphanWhenDatabaseInsertFails() {
        PhotoDao photoDao = mock(PhotoDao.class);
        OssUtil ossUtil = mock(OssUtil.class);
        ObjectProvider<OssUtil> ossUtilProvider = provider(ossUtil);
        stubSuccessfulUpload(ossUtil);
        when(photoDao.insert(any(PhotoRecord.class)))
                .thenThrow(new DataAccessResourceFailureException("database unavailable"));

        PhotoService service = new PhotoServiceImpl(ossUtilProvider, photoDao);

        Map<String, Object> response = service.uploadPhoto(photo(), "cat", "");

        assertEquals(Boolean.FALSE, response.get("success"));
        assertEquals("Upload failed: database unavailable", response.get("message"));
        verify(ossUtil).delete(capturedObjectKey(ossUtil));
    }

    @Test
    void uploadPhotoShouldCompensateOrphanWhenInsertReportsNoWrittenRow() {
        PhotoDao photoDao = mock(PhotoDao.class);
        OssUtil ossUtil = mock(OssUtil.class);
        ObjectProvider<OssUtil> ossUtilProvider = provider(ossUtil);
        stubSuccessfulUpload(ossUtil);
        when(photoDao.insert(any(PhotoRecord.class))).thenReturn(0);

        PhotoService service = new PhotoServiceImpl(ossUtilProvider, photoDao);

        Map<String, Object> response = service.uploadPhoto(photo(), "cat", "");

        assertEquals(Boolean.FALSE, response.get("success"));
        assertEquals("Upload failed: Failed to save photo record", response.get("message"));
        verify(ossUtil).delete(capturedObjectKey(ossUtil));
    }

    @Test
    void uploadPhotoShouldCleanPredeclaredKeyWhenOssResponseIsLost() {
        PhotoDao photoDao = mock(PhotoDao.class);
        OssUtil ossUtil = mock(OssUtil.class);
        ObjectProvider<OssUtil> ossUtilProvider = provider(ossUtil);
        when(ossUtil.uploadWithObjectKey(any(MultipartFile.class), anyString(), anyString()))
                .thenThrow(new IllegalStateException("OSS response lost"));

        PhotoService service = new PhotoServiceImpl(ossUtilProvider, photoDao);

        Map<String, Object> response = service.uploadPhoto(photo(), "cat", "");

        assertEquals(Boolean.FALSE, response.get("success"));
        assertEquals("Upload failed: OSS response lost", response.get("message"));
        verify(ossUtil).delete(capturedObjectKey(ossUtil));
        verify(photoDao, never()).insert(any(PhotoRecord.class));
    }

    @Test
    void uploadPhotoShouldKeepOriginalFailureWhenCleanupAlsoFails() {
        PhotoDao photoDao = mock(PhotoDao.class);
        OssUtil ossUtil = mock(OssUtil.class);
        ObjectProvider<OssUtil> ossUtilProvider = provider(ossUtil);
        stubSuccessfulUpload(ossUtil);
        DataAccessResourceFailureException databaseFailure =
                new DataAccessResourceFailureException("database unavailable");
        when(photoDao.insert(any(PhotoRecord.class))).thenThrow(databaseFailure);
        IllegalStateException cleanupFailure = new IllegalStateException("cleanup unavailable");
        doThrow(cleanupFailure).when(ossUtil).delete(anyString());

        PhotoService service = new PhotoServiceImpl(ossUtilProvider, photoDao);

        Map<String, Object> response = service.uploadPhoto(photo(), "cat", "");

        assertEquals(Boolean.FALSE, response.get("success"));
        assertEquals("Upload failed: database unavailable", response.get("message"));
        assertEquals(1, databaseFailure.getSuppressed().length);
        assertSame(cleanupFailure, databaseFailure.getSuppressed()[0]);
    }

    @Test
    void uploadPhotoShouldRejectMissingEmptyUnsupportedOrUnknownInput() {
        PhotoDao photoDao = mock(PhotoDao.class);
        OssUtil ossUtil = mock(OssUtil.class);
        ObjectProvider<OssUtil> ossUtilProvider = provider(ossUtil);
        PhotoService service = new PhotoServiceImpl(ossUtilProvider, photoDao);

        assertEquals("Please select a file",
                service.uploadPhoto(null, "cat", "").get("message"));
        assertEquals("Please select a file",
                service.uploadPhoto(new MockMultipartFile("file", "photo.jpg", "image/jpeg",
                        new byte[0]), "cat", "").get("message"));
        assertEquals("Only jpg, jpeg, png, gif and webp images are supported",
                service.uploadPhoto(file("photo.txt", "text/plain"), "cat", "").get("message"));
        assertEquals("Unsupported photo category",
                service.uploadPhoto(photo(), "unknown", "").get("message"));

        verifyNoInteractions(photoDao);
        verify(ossUtil, never()).uploadWithObjectKey(any(MultipartFile.class), anyString(), anyString());
        verify(ossUtil, never()).delete(anyString());
    }

    @Test
    void uploadPhotoShouldRejectWhenOssIsNotConfigured() {
        PhotoDao photoDao = mock(PhotoDao.class);
        ObjectProvider<OssUtil> ossUtilProvider = provider(null);

        PhotoService service = new PhotoServiceImpl(ossUtilProvider, photoDao);

        Map<String, Object> response = service.uploadPhoto(photo(), "cat", "");

        assertEquals(Boolean.FALSE, response.get("success"));
        assertEquals("OSS is not configured", response.get("message"));
        verifyNoInteractions(photoDao);
    }

    @Test
    void listPhotosShouldResolveObjectKeysWithoutChangingStoredPaths() {
        PhotoDao photoDao = mock(PhotoDao.class);
        OssUtil ossUtil = mock(OssUtil.class);
        ObjectProvider<OssUtil> ossUtilProvider = provider(ossUtil);
        PhotoRecord record = new PhotoRecord();
        record.setId(7L);
        record.setPath("love530/lovestory/photos/cat/2026/05/01/existing.jpg");
        record.setType("cat");
        record.setCreateTime(LocalDateTime.of(2026, 5, 1, 12, 30, 0));
        when(photoDao.findAll()).thenReturn(Arrays.asList(record));
        when(ossUtil.getObjectUrl(record.getPath()))
                .thenReturn("https://cdn.example/existing.jpg");

        PhotoService service = new PhotoServiceImpl(ossUtilProvider, photoDao);

        Map<String, Object> response = service.listPhotos();

        assertEquals(Boolean.TRUE, response.get("success"));
        java.util.List<?> photos = (java.util.List<?>) response.get("photos");
        assertEquals(1, photos.size());
        Map<?, ?> photo = (Map<?, ?>) photos.get(0);
        assertEquals(record.getPath(), record.getPath());
        assertEquals("https://cdn.example/existing.jpg", photo.get("url"));
        assertEquals("Cat · 2026-05-01 12:30:00", photo.get("description"));
    }

    @Test
    void deletePhotoShouldDeleteRecordBeforeOssObject() {
        PhotoDao photoDao = mock(PhotoDao.class);
        OssUtil ossUtil = mock(OssUtil.class);
        PhotoRecord record = recordWithPath(1L, "love530/lovestory/photos/cat/old.jpg");
        when(photoDao.findById(1L)).thenReturn(record);
        when(photoDao.deleteById(1L)).thenReturn(1);

        PhotoService service = new PhotoServiceImpl(provider(ossUtil), photoDao);

        Map<String, Object> response = service.deletePhoto(1L);

        assertEquals(Boolean.TRUE, response.get("success"));
        assertEquals(1L, response.get("id"));
        InOrder inOrder = inOrder(photoDao, ossUtil);
        inOrder.verify(photoDao).findById(1L);
        inOrder.verify(photoDao).deleteById(1L);
        inOrder.verify(ossUtil).delete(record.getPath());
    }

    @Test
    void deletePhotoShouldLeaveOssObjectWhenDatabaseDeleteFails() {
        PhotoDao photoDao = mock(PhotoDao.class);
        OssUtil ossUtil = mock(OssUtil.class);
        when(photoDao.findById(1L)).thenReturn(recordWithPath(1L, "old.jpg"));
        when(photoDao.deleteById(1L))
                .thenThrow(new DataAccessResourceFailureException("database unavailable"));

        PhotoService service = new PhotoServiceImpl(provider(ossUtil), photoDao);

        Map<String, Object> response = service.deletePhoto(1L);

        assertEquals(Boolean.FALSE, response.get("success"));
        assertEquals("Delete failed: database unavailable", response.get("message"));
        verify(ossUtil, never()).delete(anyString());
    }

    @Test
    void deletePhotoShouldReportCleanupFailure() {
        PhotoDao photoDao = mock(PhotoDao.class);
        OssUtil ossUtil = mock(OssUtil.class);
        when(photoDao.findById(1L)).thenReturn(recordWithPath(1L, "old.jpg"));
        when(photoDao.deleteById(1L)).thenReturn(1);
        doThrow(new IllegalStateException("OSS unavailable")).when(ossUtil).delete("old.jpg");

        PhotoService service = new PhotoServiceImpl(provider(ossUtil), photoDao);

        Map<String, Object> response = service.deletePhoto(1L);

        assertEquals(Boolean.FALSE, response.get("success"));
        assertEquals("Delete failed: OSS unavailable", response.get("message"));
        verify(photoDao).deleteById(1L);
        verify(ossUtil).delete("old.jpg");
    }

    @Test
    void deletePhotoShouldTreatConcurrentDeletionAsSuccess() {
        PhotoDao photoDao = mock(PhotoDao.class);
        OssUtil ossUtil = mock(OssUtil.class);
        when(photoDao.findById(1L)).thenReturn(
                recordWithPath(1L, "old.jpg"),
                (PhotoRecord) null);
        when(photoDao.deleteById(1L)).thenReturn(0);

        PhotoService service = new PhotoServiceImpl(provider(ossUtil), photoDao);

        Map<String, Object> response = service.deletePhoto(1L);

        assertEquals(Boolean.TRUE, response.get("success"));
        assertEquals("Photo deleted", response.get("message"));
        verify(ossUtil, never()).delete(anyString());
    }

    @Test
    void deletePhotoShouldFailWhenRecordStillExistsAfterZeroRowDelete() {
        PhotoDao photoDao = mock(PhotoDao.class);
        OssUtil ossUtil = mock(OssUtil.class);
        when(photoDao.findById(1L)).thenReturn(recordWithPath(1L, "old.jpg"));
        when(photoDao.deleteById(1L)).thenReturn(0);

        PhotoService service = new PhotoServiceImpl(provider(ossUtil), photoDao);

        Map<String, Object> response = service.deletePhoto(1L);

        assertEquals(Boolean.FALSE, response.get("success"));
        assertEquals("Failed to delete photo record", response.get("message"));
        verify(ossUtil, never()).delete(anyString());
    }

    @Test
    void deletePhotoShouldReturnNotFoundWithoutTouchingOss() {
        PhotoDao photoDao = mock(PhotoDao.class);
        OssUtil ossUtil = mock(OssUtil.class);
        when(photoDao.findById(99L)).thenReturn(null);

        PhotoService service = new PhotoServiceImpl(provider(ossUtil), photoDao);

        Map<String, Object> response = service.deletePhoto(99L);

        assertEquals(Boolean.FALSE, response.get("success"));
        assertEquals("Photo not found", response.get("message"));
        assertFalse(response.containsKey("id"));
        verify(ossUtil, never()).delete(anyString());
    }

    private PhotoRecord recordWithPath(Long id, String path) {
        PhotoRecord record = new PhotoRecord();
        record.setId(id);
        record.setPath(path);
        record.setType("cat");
        return record;
    }

    private MockMultipartFile photo() {
        return file("photo.jpg", "image/jpeg");
    }

    private MockMultipartFile file(String filename, String contentType) {
        return new MockMultipartFile("file", filename, contentType, "photo".getBytes());
    }

    private void stubSuccessfulUpload(OssUtil ossUtil) {
        when(ossUtil.uploadWithObjectKey(any(MultipartFile.class), anyString(), anyString()))
                .thenAnswer(invocation -> uploadResult(
                        invocation.getArgument(1), "https://cdn.example/photo.jpg"));
    }

    private String capturedObjectKey(OssUtil ossUtil) {
        ArgumentCaptor<String> keyCaptor = ArgumentCaptor.forClass(String.class);
        verify(ossUtil).uploadWithObjectKey(
                any(MultipartFile.class), keyCaptor.capture(), eq("image/jpeg"));
        return keyCaptor.getValue();
    }

    private OssUploadResult uploadResult(String objectKey, String url) {
        return new OssUploadResult("bucket", objectKey, url, "etag", "photo.jpg", 5L);
    }

    @SuppressWarnings("unchecked")
    private ObjectProvider<OssUtil> provider(OssUtil ossUtil) {
        ObjectProvider<OssUtil> provider = mock(ObjectProvider.class);
        when(provider.getIfAvailable()).thenReturn(ossUtil);
        return provider;
    }
}
