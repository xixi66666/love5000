package com.example.guitar.user.service;

import com.example.common.util.OssUploadResult;
import com.example.common.util.OssUtil;
import com.example.guitar.auth.model.GuitarUserPrincipal;
import com.example.guitar.storage.service.OssCleanupService;
import com.example.guitar.user.model.GuitarUser;
import com.example.guitar.web.GuitarApiException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.mock.web.MockMultipartFile;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class GuitarUserServiceImplTest {

    private GuitarUserProfilePersistenceService persistenceService;
    private ObjectProvider<OssUtil> ossUtilProvider;
    private OssCleanupService ossCleanupService;
    private GuitarUserServiceImpl service;

    @BeforeEach
    void setUp() {
        persistenceService = mock(GuitarUserProfilePersistenceService.class);
        ossUtilProvider = ossUtilProvider();
        ossCleanupService = mock(OssCleanupService.class);
        service = new GuitarUserServiceImpl(persistenceService, ossUtilProvider, ossCleanupService);
    }

    @Test
    void nicknameIsTrimmedAndMustContainOneToThirtyCharacters() {
        when(persistenceService.updateNickname(7L, "旋律"))
                .thenReturn(profileUpdate("旋律", "old/avatar.png", "old/avatar.png"));

        GuitarUserPrincipal principal = service.updateNickname(7L, "  旋律  ");

        assertThat(principal.getNickname()).isEqualTo("旋律");
        assertThat(principal.getAvatarObjectKey()).isEqualTo("old/avatar.png");
        verify(persistenceService).updateNickname(7L, "旋律");
        assertApiError(() -> service.updateNickname(7L, "   "), "VALIDATION_ERROR");
        assertApiError(() -> service.updateNickname(7L, repeat('a', 31)), "VALIDATION_ERROR");
    }

    @Test
    void avatarRequiresNonEmptyAllowedExtensionAndMatchingMagic() {
        assertApiError(() -> service.updateAvatar(7L,
                new MockMultipartFile("avatar", "empty.png", "image/png", new byte[0])), "AVATAR_FILE_INVALID");
        assertApiError(() -> service.updateAvatar(7L,
                new MockMultipartFile("avatar", "avatar.gif", "image/gif", new byte[]{'G', 'I', 'F'})), "AVATAR_FILE_INVALID");
        assertApiError(() -> service.updateAvatar(7L,
                new MockMultipartFile("avatar", "fake.PNG", "image/png", new byte[]{'G', 'I', 'F'})), "AVATAR_FILE_INVALID");
        assertApiError(() -> service.updateAvatar(7L,
                new MockMultipartFile("avatar", "fake.png", "image/png", "<svg/>".getBytes())), "AVATAR_FILE_INVALID");
    }

    @Test
    void avatarRejectsFilesLargerThanFiveMegabytes() {
        org.springframework.web.multipart.MultipartFile oversized = mock(org.springframework.web.multipart.MultipartFile.class);
        when(oversized.isEmpty()).thenReturn(false);
        when(oversized.getSize()).thenReturn(5L * 1024L * 1024L + 1L);

        assertApiError(() -> service.updateAvatar(7L, oversized), "UPLOAD_LIMIT_EXCEEDED");
        verifyNoProfilePersistence();
    }

    @Test
    void avatarFailsBeforeDatabaseMutationWhenOssIsDisabled() {
        when(ossUtilProvider.getIfAvailable()).thenReturn(null);

        assertApiError(() -> service.updateAvatar(7L, pngFile("avatar.png")), "OSS_UNAVAILABLE");
        verifyNoProfilePersistence();
    }

    @Test
    void avatarUploadsToUserScopedDirectoryThenPersistsObjectKeyAndCleansOldObject() {
        OssUtil ossUtil = mock(OssUtil.class);
        when(ossUtilProvider.getIfAvailable()).thenReturn(ossUtil);
        when(ossUtil.upload(any(java.io.InputStream.class), eq(8L), eq("avatar.png"),
                any(), eq("love530/guitar/avatars/7")))
                .thenReturn(new OssUploadResult("bucket", "new/avatar.png", "https://ignored", "etag", "avatar.png", 8));
        when(persistenceService.replaceAvatar(7L, "new/avatar.png"))
                .thenReturn(profileUpdate("旋律", "new/avatar.png", "old/avatar.png"));

        GuitarUserPrincipal principal = service.updateAvatar(7L, pngFile("../../client-name.PNG"));

        assertThat(principal.getAvatarObjectKey()).isEqualTo("new/avatar.png");
        verify(ossUtil).upload(any(java.io.InputStream.class), eq(8L), eq("avatar.png"),
                any(), eq("love530/guitar/avatars/7"));
        verify(persistenceService).replaceAvatar(7L, "new/avatar.png");
        verify(ossCleanupService).deleteOrEnqueue("old/avatar.png", "AVATAR");
    }

    @Test
    void avatarDatabaseFailureCompensatesNewObjectWithoutChangingOldAvatar() {
        OssUtil ossUtil = mock(OssUtil.class);
        when(ossUtilProvider.getIfAvailable()).thenReturn(ossUtil);
        when(ossUtil.upload(any(java.io.InputStream.class), eq(8L), eq("avatar.png"),
                any(), any())).thenReturn(new OssUploadResult("bucket", "new/avatar.png", null, null, null, 8));
        when(persistenceService.replaceAvatar(7L, "new/avatar.png"))
                .thenThrow(new GuitarApiException(org.springframework.http.HttpStatus.INTERNAL_SERVER_ERROR,
                        "PROFILE_UPDATE_FAILED", "failed"));

        assertApiError(() -> service.updateAvatar(7L, pngFile("avatar.png")), "PROFILE_UPDATE_FAILED");
        verify(ossCleanupService).deleteOrEnqueue("new/avatar.png", "AVATAR");
        verify(ossCleanupService, never()).deleteOrEnqueue("old/avatar.png", "AVATAR");
    }

    private void verifyNoProfilePersistence() {
        verify(persistenceService, never()).replaceAvatar(any(), any());
        verify(persistenceService, never()).updateNickname(any(), any());
    }

    private GuitarUserProfilePersistenceService.ProfileUpdate profileUpdate(String nickname, String avatar, String oldAvatar) {
        GuitarUser user = new GuitarUser();
        user.setId(7L);
        user.setPhone("13800138000");
        user.setNickname(nickname);
        user.setAvatarObjectKey(avatar);
        user.setRole("USER");
        return new GuitarUserProfilePersistenceService.ProfileUpdate(user, oldAvatar);
    }

    private MockMultipartFile pngFile(String filename) {
        return new MockMultipartFile("avatar", filename, "image/png",
                new byte[]{(byte) 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A});
    }

    @SuppressWarnings("unchecked")
    private ObjectProvider<OssUtil> ossUtilProvider() {
        return (ObjectProvider<OssUtil>) mock(ObjectProvider.class);
    }

    private void assertApiError(ThrowingCallable callable, String code) {
        assertThatThrownBy(callable::call).isInstanceOfSatisfying(GuitarApiException.class,
                exception -> assertThat(exception.getCode()).isEqualTo(code));
    }

    private String repeat(char value, int count) {
        StringBuilder result = new StringBuilder(count);
        for (int index = 0; index < count; index++) {
            result.append(value);
        }
        return result.toString();
    }

    @FunctionalInterface
    private interface ThrowingCallable { void call(); }
}
