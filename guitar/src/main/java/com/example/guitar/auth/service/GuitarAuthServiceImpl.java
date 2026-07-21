package com.example.guitar.auth.service;

import com.example.common.auth.service.AuthPasswordService;
import com.example.guitar.auth.dto.LoginRequest;
import com.example.guitar.auth.dto.RegisterRequest;
import com.example.guitar.auth.model.GuitarUserPrincipal;
import com.example.guitar.user.dao.GuitarUserDao;
import com.example.guitar.user.model.GuitarUser;
import com.example.guitar.web.GuitarApiException;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpSession;
import java.time.LocalDateTime;
import java.util.Optional;
import java.util.regex.Pattern;

@Service
public class GuitarAuthServiceImpl implements GuitarAuthService {

    private static final Pattern PHONE_PATTERN = Pattern.compile("^1[3-9]\\d{9}$");
    private static final int MIN_PASSWORD_LENGTH = 8;
    private static final int MAX_PASSWORD_LENGTH = 72;
    private static final int MAX_NICKNAME_LENGTH = 30;

    private final GuitarUserDao guitarUserDao;
    private final AuthPasswordService authPasswordService;

    public GuitarAuthServiceImpl(GuitarUserDao guitarUserDao, AuthPasswordService authPasswordService) {
        this.guitarUserDao = guitarUserDao;
        this.authPasswordService = authPasswordService;
    }

    @Override
    @Transactional
    public GuitarUserPrincipal register(RegisterRequest registerRequest, HttpServletRequest request) {
        if (registerRequest == null) {
            throw validationError("注册信息不能为空");
        }
        String phone = normalizePhone(registerRequest.getPhone());
        validatePhone(phone);
        validatePassword(registerRequest.getPassword());
        String nickname = normalizeNickname(registerRequest.getNickname());
        validateNickname(nickname);
        if (guitarUserDao.findByPhone(phone) != null) {
            throw new GuitarApiException(HttpStatus.BAD_REQUEST, "PHONE_EXISTS", "该手机号已注册");
        }

        GuitarUser user = new GuitarUser();
        user.setPhone(phone);
        user.setPasswordHash(authPasswordService.hash(registerRequest.getPassword()));
        user.setNickname(nickname);
        user.setRole("USER");
        user.setStatus("ENABLED");
        try {
            if (guitarUserDao.insert(user) != 1 || user.getId() == null) {
                throw new GuitarApiException(HttpStatus.INTERNAL_SERVER_ERROR,
                        "USER_CREATE_FAILED", "用户创建失败");
            }
        } catch (DuplicateKeyException exception) {
            throw new GuitarApiException(HttpStatus.BAD_REQUEST, "PHONE_EXISTS", "该手机号已注册");
        }

        GuitarUser created = guitarUserDao.findById(user.getId());
        if (created == null) {
            throw new GuitarApiException(HttpStatus.INTERNAL_SERVER_ERROR,
                    "USER_CREATE_FAILED", "用户创建失败");
        }
        GuitarUserPrincipal principal = GuitarUserPrincipal.from(created);
        rotateSession(request, principal);
        return principal;
    }

    @Override
    @Transactional
    public GuitarUserPrincipal login(LoginRequest loginRequest, HttpServletRequest request) {
        String phone = normalizePhone(loginRequest == null ? null : loginRequest.getPhone());
        String password = loginRequest == null ? null : loginRequest.getPassword();
        GuitarUser user = PHONE_PATTERN.matcher(phone).matches() ? guitarUserDao.findByPhone(phone) : null;
        if (user == null || password == null || !authPasswordService.matches(password, user.getPasswordHash())) {
            throw authFailed();
        }
        if ("BANNED".equals(user.getStatus())) {
            throw new GuitarApiException(HttpStatus.FORBIDDEN, "USER_BANNED", "账号已被封禁");
        }
        if (!"ENABLED".equals(user.getStatus())) {
            throw authFailed();
        }

        guitarUserDao.updateLastLoginAt(user.getId(), LocalDateTime.now());
        GuitarUserPrincipal principal = GuitarUserPrincipal.from(user);
        rotateSession(request, principal);
        return principal;
    }

    @Override
    public void logout(HttpServletRequest request) {
        HttpSession session = request.getSession(false);
        if (session != null) {
            session.invalidate();
        }
    }

    @Override
    public Optional<GuitarUserPrincipal> currentSession(HttpServletRequest request) {
        HttpSession session = request.getSession(false);
        if (session == null) {
            return Optional.empty();
        }
        Object value = session.getAttribute(SESSION_ATTRIBUTE);
        return value instanceof GuitarUserPrincipal
                ? Optional.of((GuitarUserPrincipal) value)
                : Optional.empty();
    }

    private void rotateSession(HttpServletRequest request, GuitarUserPrincipal principal) {
        HttpSession oldSession = request.getSession(false);
        if (oldSession != null) {
            oldSession.invalidate();
        }
        request.getSession(true).setAttribute(SESSION_ATTRIBUTE, principal);
    }

    private String normalizePhone(String phone) {
        return phone == null ? "" : phone.trim();
    }

    private void validatePhone(String phone) {
        if (!PHONE_PATTERN.matcher(phone).matches()) {
            throw new GuitarApiException(HttpStatus.BAD_REQUEST, "PHONE_INVALID", "手机号格式不正确");
        }
    }

    private void validatePassword(String password) {
        if (password == null
                || password.length() < MIN_PASSWORD_LENGTH
                || password.length() > MAX_PASSWORD_LENGTH
                || containsWhitespace(password)
                || !containsAsciiLetter(password)
                || !containsAsciiDigit(password)) {
            throw new GuitarApiException(HttpStatus.BAD_REQUEST, "PASSWORD_INVALID",
                    "密码需为 8-72 个字符，且至少包含一个英文字母和一个数字，不能包含空白字符");
        }
    }

    private String normalizeNickname(String nickname) {
        return nickname == null ? "" : nickname.trim();
    }

    private void validateNickname(String nickname) {
        if (nickname.isEmpty() || nickname.length() > MAX_NICKNAME_LENGTH) {
            throw validationError("昵称长度必须为 1-30 个字符");
        }
    }

    private boolean containsWhitespace(String value) {
        for (int index = 0; index < value.length(); index++) {
            char current = value.charAt(index);
            if (Character.isWhitespace(current) || Character.isSpaceChar(current) || current == '\u0085') {
                return true;
            }
        }
        return false;
    }

    private boolean containsAsciiLetter(String value) {
        for (int index = 0; index < value.length(); index++) {
            char current = value.charAt(index);
            if ((current >= 'A' && current <= 'Z') || (current >= 'a' && current <= 'z')) {
                return true;
            }
        }
        return false;
    }

    private boolean containsAsciiDigit(String value) {
        for (int index = 0; index < value.length(); index++) {
            char current = value.charAt(index);
            if (current >= '0' && current <= '9') {
                return true;
            }
        }
        return false;
    }

    private GuitarApiException validationError(String message) {
        return new GuitarApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", message);
    }

    private GuitarApiException authFailed() {
        return new GuitarApiException(HttpStatus.UNAUTHORIZED, "AUTH_FAILED", "手机号或密码错误");
    }
}
