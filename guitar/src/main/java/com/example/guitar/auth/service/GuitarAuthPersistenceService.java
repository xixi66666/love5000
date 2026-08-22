package com.example.guitar.auth.service;

import com.example.guitar.user.dao.GuitarUserDao;
import com.example.guitar.user.model.GuitarUser;
import com.example.guitar.web.GuitarApiException;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

@Service
public class GuitarAuthPersistenceService {

    private final GuitarUserDao guitarUserDao;

    public GuitarAuthPersistenceService(GuitarUserDao guitarUserDao) {
        this.guitarUserDao = guitarUserDao;
    }

    @Transactional(readOnly = true)
    public GuitarUser findByPhone(String phone) {
        return guitarUserDao.findByPhone(phone);
    }

    @Transactional
    public GuitarUser createUser(GuitarUser user) {
        if (guitarUserDao.findByPhone(user.getPhone()) != null) {
            throw phoneExists();
        }
        try {
            if (guitarUserDao.insert(user) != 1 || user.getId() == null) {
                throw new GuitarApiException(HttpStatus.INTERNAL_SERVER_ERROR,
                        "USER_CREATE_FAILED", "用户创建失败");
            }
        } catch (DuplicateKeyException exception) {
            throw phoneExists();
        }
        GuitarUser created = guitarUserDao.findById(user.getId());
        if (created == null) {
            throw new GuitarApiException(HttpStatus.INTERNAL_SERVER_ERROR,
                    "USER_CREATE_FAILED", "用户创建失败");
        }
        return created;
    }

    @Transactional
    public void recordSuccessfulLogin(Long userId) {
        if (guitarUserDao.updateLastLoginAt(userId, LocalDateTime.now()) != 1) {
            throw new GuitarApiException(HttpStatus.INTERNAL_SERVER_ERROR,
                    "AUTH_STATE_UPDATE_FAILED", "登录状态更新失败");
        }
    }

    private GuitarApiException phoneExists() {
        return new GuitarApiException(HttpStatus.BAD_REQUEST, "PHONE_EXISTS", "该手机号已注册");
    }
}
