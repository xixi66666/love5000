package com.example.guitar.user.service;

import com.example.guitar.user.dao.GuitarUserDao;
import com.example.guitar.user.model.GuitarUser;
import com.example.guitar.web.GuitarApiException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class GuitarUserProfilePersistenceServiceTest {

    private GuitarUserDao guitarUserDao;
    private GuitarUserProfilePersistenceService service;

    @BeforeEach
    void setUp() {
        guitarUserDao = mock(GuitarUserDao.class);
        service = new GuitarUserProfilePersistenceService(guitarUserDao);
    }

    @Test
    void profileUpdateRequiresExactlyOneAffectedRowAndReturnsReloadedUser() {
        GuitarUser current = user("old", "old/avatar.png");
        GuitarUser updated = user("new", "old/avatar.png");
        when(guitarUserDao.findByIdForUpdate(7L)).thenReturn(current);
        when(guitarUserDao.updateProfile(7L, "new", "old/avatar.png")).thenReturn(1);
        when(guitarUserDao.findById(7L)).thenReturn(updated);

        GuitarUserProfilePersistenceService.ProfileUpdate result = service.updateNickname(7L, "new");

        assertThat(result.getUser().getNickname()).isEqualTo("new");
        assertThat(result.getPreviousAvatarObjectKey()).isEqualTo("old/avatar.png");
        verify(guitarUserDao).updateProfile(7L, "new", "old/avatar.png");
    }

    @Test
    void profileUpdateRejectsZeroOrMultipleAffectedRows() {
        when(guitarUserDao.findByIdForUpdate(7L)).thenReturn(user("old", null));
        when(guitarUserDao.updateProfile(eq(7L), eq("new"), eq(null))).thenReturn(0);

        assertThatThrownBy(() -> service.updateNickname(7L, "new"))
                .isInstanceOfSatisfying(GuitarApiException.class,
                        exception -> assertThat(exception.getCode()).isEqualTo("PROFILE_UPDATE_FAILED"));
    }

    @Test
    void profileUpdateRejectsMissingReloadAfterDatabaseUpdate() {
        when(guitarUserDao.findByIdForUpdate(7L)).thenReturn(user("old", "old/avatar.png"));
        when(guitarUserDao.updateProfile(7L, "new", "old/avatar.png")).thenReturn(1);
        when(guitarUserDao.findById(7L)).thenReturn(null);

        assertThatThrownBy(() -> service.updateNickname(7L, "new"))
                .isInstanceOfSatisfying(GuitarApiException.class,
                        exception -> assertThat(exception.getCode()).isEqualTo("PROFILE_UPDATE_FAILED"));
    }

    private GuitarUser user(String nickname, String avatar) {
        GuitarUser user = new GuitarUser();
        user.setId(7L);
        user.setNickname(nickname);
        user.setAvatarObjectKey(avatar);
        user.setRole("USER");
        return user;
    }
}
