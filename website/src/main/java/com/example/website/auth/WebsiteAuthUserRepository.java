package com.example.website.auth;

import com.example.common.auth.model.AuthUser;
import com.example.common.auth.repository.AuthUserRepository;
import com.example.website.auth.dao.WebsiteAuthUserDao;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public class WebsiteAuthUserRepository implements AuthUserRepository {

    private final WebsiteAuthUserDao websiteAuthUserDao;

    public WebsiteAuthUserRepository(WebsiteAuthUserDao websiteAuthUserDao) {
        this.websiteAuthUserDao = websiteAuthUserDao;
    }

    @Override
    public Optional<AuthUser> findByUsername(String username) {
        return Optional.ofNullable(websiteAuthUserDao.findByUsername(username));
    }

    @Override
    public Optional<AuthUser> findById(Long id) {
        return Optional.ofNullable(websiteAuthUserDao.findById(id));
    }

    @Override
    public Long save(String username, String passwordHash, String displayName, String role) {
        AuthUser authUser = new AuthUser();
        authUser.setUsername(username);
        authUser.setPasswordHash(passwordHash);
        authUser.setDisplayName(displayName);
        authUser.setRole(role);
        websiteAuthUserDao.insert(authUser);
        return authUser.getId();
    }
}
