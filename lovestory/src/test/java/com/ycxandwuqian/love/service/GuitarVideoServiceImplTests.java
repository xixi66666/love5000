package com.ycxandwuqian.love.service;

import com.example.common.util.OssUploadResult;
import com.example.common.util.OssUtil;
import com.ycxandwuqian.love.dao.GuitarVideoDao;
import com.ycxandwuqian.love.model.GuitarVideoRecord;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.mock.web.MockMultipartFile;

import java.time.LocalDateTime;
import java.util.Arrays;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class GuitarVideoServiceImplTests {

    @Test
    void listVisibleVideosShouldReturnCardResponses() {
        GuitarVideoDao guitarVideoDao = mock(GuitarVideoDao.class);
        ObjectProvider<OssUtil> ossUtilProvider = mock(ObjectProvider.class);
        GuitarVideoRecord record = new GuitarVideoRecord();
        record.setId(7L);
        record.setTitle("弹给你的第一首歌");
        record.setDescription("今天先弹这一段");
        record.setTag("吉他弹唱");
        record.setVideoUrl("https://example.com/video.mp4");
        record.setCoverUrl("https://example.com/cover.jpg");
        record.setDurationSeconds(95);
        record.setSortOrder(10);
        record.setCreateTime(LocalDateTime.of(2026, 5, 28, 20, 30, 0));
        when(guitarVideoDao.findVisible()).thenReturn(Arrays.asList(record));

        GuitarVideoService service = new GuitarVideoServiceImpl(ossUtilProvider, guitarVideoDao);

        Map<String, Object> response = service.listVideos();

        assertEquals(true, response.get("success"));
        List<?> videos = (List<?>) response.get("videos");
        assertEquals(1, videos.size());
        Map<?, ?> video = (Map<?, ?>) videos.get(0);
        assertEquals(7L, video.get("id"));
        assertEquals("弹给你的第一首歌", video.get("title"));
        assertEquals("https://example.com/video.mp4", video.get("videoUrl"));
        assertEquals("2026-05-28 20:30:00", video.get("createTime"));
    }

    @Test
    void uploadVideoShouldUploadToOssAndInsertRecord() {
        GuitarVideoDao guitarVideoDao = mock(GuitarVideoDao.class);
        ObjectProvider<OssUtil> ossUtilProvider = mock(ObjectProvider.class);
        OssUtil ossUtil = mock(OssUtil.class);
        when(ossUtilProvider.getIfAvailable()).thenReturn(ossUtil);
        when(ossUtil.upload(any(MockMultipartFile.class), eq("love530/lovestory/videos")))
                .thenReturn(new OssUploadResult("bucket", "videos/guitar.mp4", "https://example.com/guitar.mp4", "etag", "guitar.mp4", 12L));
        when(ossUtil.upload(any(MockMultipartFile.class), eq("love530/lovestory/videos/covers")))
                .thenReturn(new OssUploadResult("bucket", "covers/guitar.jpg", "https://example.com/guitar.jpg", "etag", "cover.jpg", 4L));
        MockMultipartFile file = new MockMultipartFile("file", "guitar.mp4", "video/mp4", "video".getBytes());
        MockMultipartFile cover = new MockMultipartFile("cover", "cover.jpg", "image/jpeg", "cover".getBytes());

        GuitarVideoService service = new GuitarVideoServiceImpl(ossUtilProvider, guitarVideoDao);

        Map<String, Object> response = service.uploadVideo(file, cover, "  小星星  ", "  送给你  ", "  吉他弹唱  ", 8);

        assertEquals(true, response.get("success"));
        assertEquals("Upload succeeded", response.get("message"));
        assertNotNull(response.get("video"));
        verify(guitarVideoDao).insert(any(GuitarVideoRecord.class));
    }

    @Test
    void uploadVideoShouldRejectBlankTitle() {
        GuitarVideoDao guitarVideoDao = mock(GuitarVideoDao.class);
        ObjectProvider<OssUtil> ossUtilProvider = mock(ObjectProvider.class);
        MockMultipartFile file = new MockMultipartFile("file", "guitar.mp4", "video/mp4", "video".getBytes());

        GuitarVideoService service = new GuitarVideoServiceImpl(ossUtilProvider, guitarVideoDao);

        Map<String, Object> response = service.uploadVideo(file, null, "   ", "", "", null);

        assertEquals(false, response.get("success"));
        assertEquals("Video title must not be blank", response.get("message"));
        verify(guitarVideoDao, never()).insert(any(GuitarVideoRecord.class));
    }

    @Test
    void uploadVideoShouldRejectUnsupportedVideoExtension() {
        GuitarVideoDao guitarVideoDao = mock(GuitarVideoDao.class);
        ObjectProvider<OssUtil> ossUtilProvider = mock(ObjectProvider.class);
        MockMultipartFile file = new MockMultipartFile("file", "guitar.txt", "text/plain", "bad".getBytes());

        GuitarVideoService service = new GuitarVideoServiceImpl(ossUtilProvider, guitarVideoDao);

        Map<String, Object> response = service.uploadVideo(file, null, "小星星", "", "", null);

        assertEquals(false, response.get("success"));
        assertEquals("Only mp4, webm and mov videos are supported", response.get("message"));
        verify(guitarVideoDao, never()).insert(any(GuitarVideoRecord.class));
    }

    @Test
    void deleteVideoShouldDeleteOssObjectsAndHideRecord() {
        GuitarVideoDao guitarVideoDao = mock(GuitarVideoDao.class);
        ObjectProvider<OssUtil> ossUtilProvider = mock(ObjectProvider.class);
        OssUtil ossUtil = mock(OssUtil.class);
        GuitarVideoRecord record = new GuitarVideoRecord();
        record.setId(3L);
        record.setVideoUrl("https://example.com/video.mp4");
        record.setCoverUrl("https://example.com/cover.jpg");
        when(guitarVideoDao.findById(3L)).thenReturn(record);
        when(guitarVideoDao.hideById(3L)).thenReturn(1);
        when(ossUtilProvider.getIfAvailable()).thenReturn(ossUtil);

        GuitarVideoService service = new GuitarVideoServiceImpl(ossUtilProvider, guitarVideoDao);

        Map<String, Object> response = service.deleteVideo(3L);

        assertEquals(true, response.get("success"));
        assertEquals(3L, response.get("id"));
        verify(ossUtil).delete("https://example.com/video.mp4");
        verify(ossUtil).delete("https://example.com/cover.jpg");
        verify(guitarVideoDao).hideById(3L);
    }

    @Test
    void deleteVideoShouldReturnNotFoundWhenRecordMissing() {
        GuitarVideoDao guitarVideoDao = mock(GuitarVideoDao.class);
        ObjectProvider<OssUtil> ossUtilProvider = mock(ObjectProvider.class);
        when(guitarVideoDao.findById(99L)).thenReturn(null);

        GuitarVideoService service = new GuitarVideoServiceImpl(ossUtilProvider, guitarVideoDao);

        Map<String, Object> response = service.deleteVideo(99L);

        assertEquals(false, response.get("success"));
        assertEquals("Video not found", response.get("message"));
        assertFalse(response.containsKey("id"));
    }

    @Test
    void uploadCoverShouldUploadCoverAndUpdateRecord() {
        GuitarVideoDao guitarVideoDao = mock(GuitarVideoDao.class);
        ObjectProvider<OssUtil> ossUtilProvider = mock(ObjectProvider.class);
        OssUtil ossUtil = mock(OssUtil.class);
        GuitarVideoRecord record = new GuitarVideoRecord();
        record.setId(1L);
        record.setTitle("忽然之间");
        record.setVideoUrl("https://example.com/video.mp4");
        when(guitarVideoDao.findById(1L)).thenReturn(record);
        when(ossUtilProvider.getIfAvailable()).thenReturn(ossUtil);
        when(ossUtil.upload(any(MockMultipartFile.class), eq("love530/lovestory/videos/covers")))
                .thenReturn(new OssUploadResult("bucket", "covers/generated.jpg", "https://example.com/generated.jpg", "etag", "generated.jpg", 20L));
        when(guitarVideoDao.updateCoverUrl(1L, "https://example.com/generated.jpg")).thenReturn(1);
        MockMultipartFile cover = new MockMultipartFile("cover", "generated.jpg", "image/jpeg", "cover".getBytes());

        GuitarVideoService service = new GuitarVideoServiceImpl(ossUtilProvider, guitarVideoDao);

        Map<String, Object> response = service.uploadCover(1L, cover);

        assertEquals(true, response.get("success"));
        Map<?, ?> video = (Map<?, ?>) response.get("video");
        assertEquals("https://example.com/generated.jpg", video.get("coverUrl"));
        verify(guitarVideoDao).updateCoverUrl(1L, "https://example.com/generated.jpg");
    }
}
