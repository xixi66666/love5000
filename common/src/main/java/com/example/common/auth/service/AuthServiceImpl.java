package com.example.common.auth.service;

import com.example.common.auth.config.AuthProperties;
import com.example.common.auth.dto.AuthRequest;
import com.example.common.auth.exception.AuthException;
import com.example.common.auth.model.AuthUser;
import com.example.common.auth.model.AuthUserPrincipal;
import com.example.common.auth.repository.AuthUserRepository;
import org.springframework.http.HttpStatus;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import javax.servlet.http.HttpSession;
import java.util.Locale;
import java.util.Optional;
import java.util.regex.Pattern;

public class AuthServiceImpl implements AuthService {

    private static final Pattern USERNAME_PATTERN = Pattern.compile("^[a-zA-Z0-9_]{3,32}$");

    private final AuthUserRepository authUserRepository;

    private final AuthPasswordService authPasswordService;

    private final AuthProperties authProperties;

    public AuthServiceImpl(AuthUserRepository authUserRepository,
                           AuthPasswordService authPasswordService,
                           AuthProperties authProperties) {
        this.authUserRepository = authUserRepository;
        this.authPasswordService = authPasswordService;
        this.authProperties = authProperties;
    }

    @Override
    public AuthUserPrincipal register(AuthRequest authRequest, HttpServletRequest request) {
        String username = normalizeUsername(authRequest.getUsername());
        validateUsername(username);
        validatePassword(authRequest.getPassword());
        if (authUserRepository.findByUsername(username).isPresent()) {
            throw new AuthException(HttpStatus.BAD_REQUEST, "Username already exists");
        }
        String displayName = normalizeDisplayName(authRequest.getDisplayName(), username);
        Long id = authUserRepository.save(username, authPasswordService.hash(authRequest.getPassword()), displayName, "USER");
        AuthUser authUser = authUserRepository.findById(id)
                .orElseThrow(() -> new AuthException(HttpStatus.INTERNAL_SERVER_ERROR, "Failed to load created user"));
        AuthUserPrincipal principal = AuthUserPrincipal.from(authUser);
        savePrincipal(request, principal);
        return principal;
    }

    @Override
    public AuthUserPrincipal login(AuthRequest authRequest, HttpServletRequest request) {
        String username = normalizeUsername(authRequest.getUsername());
        AuthUser authUser = authUserRepository.findByUsername(username)
                .orElseThrow(() -> new AuthException(HttpStatus.UNAUTHORIZED, "Invalid username or password"));
        if (!authUser.isEnabled() || !authPasswordService.matches(authRequest.getPassword(), authUser.getPasswordHash())) {
            throw new AuthException(HttpStatus.UNAUTHORIZED, "Invalid username or password");
        }
        AuthUserPrincipal principal = AuthUserPrincipal.from(authUser);
        savePrincipal(request, principal);
        return principal;
    }

    @Override
    public void logout(HttpServletRequest request, HttpServletResponse response) {
        HttpSession session = request.getSession(false);
        if (session != null) {
            session.invalidate();
        }
    }

    @Override
    public Optional<AuthUserPrincipal> currentUser(HttpServletRequest request) {
        HttpSession session = request.getSession(false);
        if (session == null) {
            return Optional.empty();
        }
        Object user = session.getAttribute(authProperties.getSessionAttribute());
        if (user instanceof AuthUserPrincipal) {
            return Optional.of((AuthUserPrincipal) user);
        }
        return Optional.empty();
    }

    @Override
    public AuthUserPrincipal requireCurrentUser(HttpServletRequest request) {
        return currentUser(request).orElseThrow(() -> new AuthException(HttpStatus.UNAUTHORIZED, "Login required"));
    }

    private void savePrincipal(HttpServletRequest request, AuthUserPrincipal principal) {
        HttpSession oldSession = request.getSession(false);
        if (oldSession != null) {
            oldSession.invalidate();
        }
        request.getSession(true).setAttribute(authProperties.getSessionAttribute(), principal);
    }

    private String normalizeUsername(String username) {
        return username == null ? "" : username.trim().toLowerCase(Locale.ROOT);
    }

    private String normalizeDisplayName(String displayName, String username) {
        if (displayName == null || displayName.trim().isEmpty()) {
            return username;
        }
        return displayName.trim();
    }

    private void validateUsername(String username) {
        if (!USERNAME_PATTERN.matcher(username).matches()) {
            throw new AuthException(HttpStatus.BAD_REQUEST, "Username must be 3-32 characters and contain only letters, numbers, or underscore");
        }
    }

    private void validatePassword(String password) {
        if (password == null || password.length() < authProperties.getMinPasswordLength()) {
            throw new AuthException(HttpStatus.BAD_REQUEST, "Password is too short");
        }
    }
}
