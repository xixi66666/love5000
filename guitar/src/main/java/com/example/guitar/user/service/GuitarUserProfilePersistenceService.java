package com.example.guitar.user.service;

import com.example.guitar.user.dao.GuitarUserDao;
import com.example.guitar.user.model.GuitarUser;
import com.example.guitar.web.GuitarApiException;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class GuitarUserProfilePersistenceService {

    private final GuitarUserDao guitarUserDao;

    public GuitarUserProfilePersistenceService(GuitarUserDao guitarUserDao) {
        this.guitarUserDao = guitarUserDao;
    }

    @Transactional
    public ProfileUpdate updateNickname(Long userId, String nickname) {
        GuitarUser current = requireCurrentUser(userId);
        return updateAndReload(userId, nickname, current.getAvatarObjectKey(), current.getAvatarObjectKey());
    }

    @Transactional
    public ProfileUpdate replaceAvatar(Long userId, String avatarObjectKey) {
        GuitarUser current = requireCurrentUser(userId);
        return updateAndReload(userId, current.getNickname(), avatarObjectKey, current.getAvatarObjectKey());
    }

    private GuitarUser requireCurrentUser(Long userId) {
        GuitarUser current = guitarUserDao.findByIdForUpdate(userId);
        if (current == null) {
            throw profileUpdateFailed();
        }
        return current;
    }

    private ProfileUpdate updateAndReload(Long userId, String nickname, String avatarObjectKey,
                                          String previousAvatarObjectKey) {
        if (guitarUserDao.updateProfile(userId, nickname, avatarObjectKey) != 1) {
            throw profileUpdateFailed();
        }
        GuitarUser updated = guitarUserDao.findById(userId);
        if (updated == null) {
            throw profileUpdateFailed();
        }
        return new ProfileUpdate(updated, previousAvatarObjectKey);
    }

    private GuitarApiException profileUpdateFailed() {
        return new GuitarApiException(HttpStatus.INTERNAL_SERVER_ERROR,
                "PROFILE_UPDATE_FAILED", "用户资料更新失败，请稍后重试");
    }

    public static final class ProfileUpdate {

        private final GuitarUser user;
        private final String previousAvatarObjectKey;

        public ProfileUpdate(GuitarUser user, String previousAvatarObjectKey) {
            this.user = user;
            this.previousAvatarObjectKey = previousAvatarObjectKey;
        }

        public GuitarUser getUser() {
            return user;
        }

        public String getPreviousAvatarObjectKey() {
            return previousAvatarObjectKey;
        }
    }
}
