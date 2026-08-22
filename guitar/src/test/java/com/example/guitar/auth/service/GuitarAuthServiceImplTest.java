package com.example.guitar.auth.service;

import com.example.common.auth.service.AuthPasswordService;
import com.example.guitar.auth.dto.LoginRequest;
import com.example.guitar.auth.dto.RegisterRequest;
import com.example.guitar.auth.model.GuitarUserPrincipal;
import com.example.guitar.user.dao.GuitarUserDao;
import com.example.guitar.user.model.GuitarUser;
import com.example.guitar.web.GuitarApiException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.mockito.ArgumentCaptor;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpSession;
import org.springframework.transaction.TransactionSystemException;

import javax.servlet.http.HttpSession;
import java.time.LocalDateTime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.reset;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class GuitarAuthServiceImplTest {

    private GuitarUserDao guitarUserDao;

    private AuthPasswordService authPasswordService;

    private GuitarAuthServiceImpl authService;

    @BeforeEach
    void setUp() {
        guitarUserDao = mock(GuitarUserDao.class);
        authPasswordService = new AuthPasswordService();
        authService = new GuitarAuthServiceImpl(
                new GuitarAuthPersistenceService(guitarUserDao), authPasswordService);
    }

    @Test
    void registerCreatesEnabledUserWithHashedPasswordAndRotatedSession() {
        MockHttpServletRequest request = new MockHttpServletRequest();
        MockHttpSession oldSession = (MockHttpSession) request.getSession(true);
        when(guitarUserDao.findByPhone("13800138000")).thenReturn(null);
        doAnswer(invocation -> {
            GuitarUser inserted = invocation.getArgument(0);
            inserted.setId(42L);
            return 1;
        }).when(guitarUserDao).insert(any(GuitarUser.class));
        when(guitarUserDao.findById(42L)).thenAnswer(invocation -> {
            ArgumentCaptor<GuitarUser> captor = ArgumentCaptor.forClass(GuitarUser.class);
            verify(guitarUserDao).insert(captor.capture());
            return captor.getValue();
        });

        GuitarUserPrincipal principal = authService.register(
                registerRequest(" 13800138000 ", "guitar123", " 小吉他 "), request);

        ArgumentCaptor<GuitarUser> captor = ArgumentCaptor.forClass(GuitarUser.class);
        verify(guitarUserDao).insert(captor.capture());
        GuitarUser inserted = captor.getValue();
        assertThat(inserted.getPhone()).isEqualTo("13800138000");
        assertThat(inserted.getNickname()).isEqualTo("小吉他");
        assertThat(inserted.getRole()).isEqualTo("USER");
        assertThat(inserted.getStatus()).isEqualTo("ENABLED");
        assertThat(inserted.getPasswordHash()).isNotEqualTo("guitar123");
        assertThat(authPasswordService.matches("guitar123", inserted.getPasswordHash())).isTrue();
        assertThat(principal.getId()).isEqualTo(42L);
        assertThat(oldSession.isInvalid()).isTrue();
        assertThat(request.getSession(false)).isNotSameAs(oldSession);
        assertThat(request.getSession(false).getAttribute(GuitarAuthService.SESSION_ATTRIBUTE))
                .isEqualTo(principal);
    }

    @ParameterizedTest
    @ValueSource(strings = {"", "12800138000", "1380013800", "138001380000", "1380013a000"})
    void registerRejectsInvalidMainlandPhone(String phone) {
        assertApiError(
                () -> authService.register(registerRequest(phone, "guitar123", "用户"),
                        new MockHttpServletRequest()),
                HttpStatus.BAD_REQUEST,
                "PHONE_INVALID");
        verify(guitarUserDao, never()).insert(any(GuitarUser.class));
    }

    @Test
    void registerRejectsDuplicatePhoneWithStableCode() {
        when(guitarUserDao.findByPhone("13800138000")).thenReturn(user(1L, "13800138000", "hash", "USER", "ENABLED"));

        assertApiError(
                () -> authService.register(registerRequest("13800138000", "guitar123", "用户"),
                        new MockHttpServletRequest()),
                HttpStatus.BAD_REQUEST,
                "PHONE_EXISTS");
    }

    @ParameterizedTest
    @ValueSource(strings = {"short1", "abcdefgh", "12345678", "guitar 123", "guitar\u00a0123", "guitar\u0085123"})
    void registerRejectsWeakPassword(String password) {
        assertApiError(
                () -> authService.register(registerRequest("13800138000", password, "用户"),
                        new MockHttpServletRequest()),
                HttpStatus.BAD_REQUEST,
                "PASSWORD_INVALID");
        verify(guitarUserDao, never()).insert(any(GuitarUser.class));
    }

    @Test
    void registerRejectsPasswordLongerThanBcryptLimit() {
        assertApiError(
                () -> authService.register(registerRequest("13800138000", repeat('a', 72) + "1", "用户"),
                        new MockHttpServletRequest()),
                HttpStatus.BAD_REQUEST,
                "PASSWORD_INVALID");
        verify(guitarUserDao, never()).insert(any(GuitarUser.class));
    }

    @Test
    void registerRejectsPasswordLongerThanSeventyTwoUtf8Bytes() {
        String password = repeat('a', 69) + "吉1";

        assertApiError(
                () -> authService.register(registerRequest("13800138000", password, "用户"),
                        new MockHttpServletRequest()),
                HttpStatus.BAD_REQUEST,
                "PASSWORD_INVALID");
        verify(guitarUserDao, never()).insert(any(GuitarUser.class));
    }

    @Test
    void registerAcceptsEightAndSeventyTwoCharacterPasswords() {
        assertRegisterSucceeds("guitar12", 42L);
        assertRegisterSucceeds(repeat('a', 71) + "1", 43L);
    }

    @Test
    void registerRejectsBlankNicknameAsValidationError() {
        assertApiError(
                () -> authService.register(registerRequest("13800138000", "guitar123", "   "),
                        new MockHttpServletRequest()),
                HttpStatus.BAD_REQUEST,
                "VALIDATION_ERROR");
    }

    @Test
    void registerRejectsNicknameLongerThanThirtyCharacters() {
        assertApiError(
                () -> authService.register(registerRequest("13800138000", "guitar123", repeat('吉', 31)),
                        new MockHttpServletRequest()),
                HttpStatus.BAD_REQUEST,
                "VALIDATION_ERROR");
        verify(guitarUserDao, never()).insert(any(GuitarUser.class));
    }

    @Test
    void registerMapsConcurrentDuplicateInsertToStableError() {
        when(guitarUserDao.findByPhone("13800138000")).thenReturn(null);
        when(guitarUserDao.insert(any(GuitarUser.class)))
                .thenThrow(new DuplicateKeyException("uk_guitar_user_phone"));

        assertApiError(
                () -> authService.register(registerRequest("13800138000", "guitar123", "用户"),
                        new MockHttpServletRequest()),
                HttpStatus.BAD_REQUEST,
                "PHONE_EXISTS");
    }

    @Test
    void loginUsesGenericFailureForMissingPhoneAndWrongPassword() {
        when(guitarUserDao.findByPhone("13800138000")).thenReturn(null);
        assertApiError(
                () -> authService.login(loginRequest("13800138000", "wrong123"),
                        new MockHttpServletRequest()),
                HttpStatus.UNAUTHORIZED,
                "AUTH_FAILED");

        GuitarUser existing = user(7L, "13900139000", authPasswordService.hash("right123"), "USER", "ENABLED");
        when(guitarUserDao.findByPhone("13900139000")).thenReturn(existing);
        assertApiError(
                () -> authService.login(loginRequest("13900139000", "wrong123"),
                        new MockHttpServletRequest()),
                HttpStatus.UNAUTHORIZED,
                "AUTH_FAILED");
        verify(guitarUserDao, never()).updateLastLoginAt(any(Long.class), any(LocalDateTime.class));
    }

    @Test
    void loginRejectsSeventyThreeByteBcryptSuffixCollision() {
        String seventyTwoBytes = repeat('a', 71) + "1";
        GuitarUser existing = user(7L, "13800138000", authPasswordService.hash(seventyTwoBytes), "USER", "ENABLED");
        when(guitarUserDao.findByPhone("13800138000")).thenReturn(existing);

        assertApiError(
                () -> authService.login(loginRequest("13800138000", seventyTwoBytes + "x"),
                        new MockHttpServletRequest()),
                HttpStatus.UNAUTHORIZED,
                "AUTH_FAILED");
        verify(guitarUserDao, never()).updateLastLoginAt(any(Long.class), any(LocalDateTime.class));
    }

    @Test
    void missingAndMalformedPhonesStillPerformDummyPasswordMatch() {
        AuthPasswordService passwordService = mock(AuthPasswordService.class);
        GuitarAuthServiceImpl timingSafeService = new GuitarAuthServiceImpl(
                new GuitarAuthPersistenceService(guitarUserDao), passwordService);
        when(passwordService.matches(anyString(), anyString())).thenReturn(false);

        assertApiError(
                () -> timingSafeService.login(loginRequest("13800138000", "wrong123"),
                        new MockHttpServletRequest()),
                HttpStatus.UNAUTHORIZED,
                "AUTH_FAILED");
        assertApiError(
                () -> timingSafeService.login(loginRequest("bad-phone", "wrong123"),
                        new MockHttpServletRequest()),
                HttpStatus.UNAUTHORIZED,
                "AUTH_FAILED");

        verify(passwordService, org.mockito.Mockito.times(2))
                .matches(eq("wrong123"), argThat(hash -> hash != null && hash.startsWith("$2")));
    }

    @Test
    void disabledUserWithoutUsableHashPerformsDummyMatchAndFailsGenerically() {
        AuthPasswordService passwordService = mock(AuthPasswordService.class);
        GuitarAuthServiceImpl timingSafeService = new GuitarAuthServiceImpl(
                new GuitarAuthPersistenceService(guitarUserDao), passwordService);
        when(guitarUserDao.findByPhone("13800138000"))
                .thenReturn(user(7L, "13800138000", null, "USER", "DISABLED"));
        when(passwordService.matches(anyString(), anyString())).thenReturn(false);

        assertApiError(
                () -> timingSafeService.login(loginRequest("13800138000", "wrong123"),
                        new MockHttpServletRequest()),
                HttpStatus.UNAUTHORIZED,
                "AUTH_FAILED");

        verify(passwordService).matches(eq("wrong123"), argThat(hash -> hash != null && hash.startsWith("$2")));
    }

    @Test
    void loginUsesGenericFailureForDisabledUser() {
        GuitarUser disabled = user(7L, "13800138000", authPasswordService.hash("right123"), "USER", "DISABLED");
        when(guitarUserDao.findByPhone("13800138000")).thenReturn(disabled);

        assertApiError(
                () -> authService.login(loginRequest("13800138000", "right123"),
                        new MockHttpServletRequest()),
                HttpStatus.UNAUTHORIZED,
                "AUTH_FAILED");
        verify(guitarUserDao, never()).updateLastLoginAt(any(Long.class), any(LocalDateTime.class));
    }

    @Test
    void loginRejectsBannedUserAfterValidPassword() {
        GuitarUser banned = user(7L, "13800138000", authPasswordService.hash("right123"), "USER", "BANNED");
        when(guitarUserDao.findByPhone("13800138000")).thenReturn(banned);

        assertApiError(
                () -> authService.login(loginRequest("13800138000", "right123"),
                        new MockHttpServletRequest()),
                HttpStatus.FORBIDDEN,
                "USER_BANNED");
        verify(guitarUserDao, never()).updateLastLoginAt(any(Long.class), any(LocalDateTime.class));
    }

    @Test
    void loginUpdatesLastLoginAndRotatesSession() {
        GuitarUser existing = user(7L, "13800138000", authPasswordService.hash("right123"), "USER", "ENABLED");
        existing.setNickname("旋律");
        when(guitarUserDao.findByPhone("13800138000")).thenReturn(existing);
        when(guitarUserDao.updateLastLoginAt(eq(7L), any(LocalDateTime.class))).thenReturn(1);
        MockHttpServletRequest request = new MockHttpServletRequest();
        MockHttpSession oldSession = (MockHttpSession) request.getSession(true);

        GuitarUserPrincipal principal = authService.login(loginRequest(" 13800138000 ", "right123"), request);

        verify(guitarUserDao).updateLastLoginAt(eq(7L), any(LocalDateTime.class));
        assertThat(principal.getPhone()).isEqualTo("13800138000");
        assertThat(oldSession.isInvalid()).isTrue();
        assertThat(request.getSession(false).getAttribute(GuitarAuthService.SESSION_ATTRIBUTE))
                .isEqualTo(principal);
    }

    @Test
    void registrationCommitFailureLeavesAnonymousSessionUnauthenticated() {
        GuitarAuthPersistenceService persistenceService = mock(GuitarAuthPersistenceService.class);
        GuitarAuthServiceImpl service = new GuitarAuthServiceImpl(persistenceService, authPasswordService);
        MockHttpServletRequest request = new MockHttpServletRequest();
        MockHttpSession originalSession = (MockHttpSession) request.getSession(true);
        when(persistenceService.createUser(any(GuitarUser.class)))
                .thenThrow(new TransactionSystemException("simulated commit failure"));

        assertThatThrownBy(() -> service.register(
                registerRequest("13800138000", "guitar123", "用户"), request))
                .isInstanceOf(TransactionSystemException.class);

        assertThat(originalSession.isInvalid()).isFalse();
        assertThat(originalSession.getAttribute(GuitarAuthService.SESSION_ATTRIBUTE)).isNull();
        assertThat(request.getSession(false)).isSameAs(originalSession);
    }

    @Test
    void loginCommitFailureLeavesAnonymousSessionUnauthenticated() {
        GuitarAuthPersistenceService persistenceService = mock(GuitarAuthPersistenceService.class);
        GuitarAuthServiceImpl service = new GuitarAuthServiceImpl(persistenceService, authPasswordService);
        GuitarUser existing = user(7L, "13800138000", authPasswordService.hash("right123"), "USER", "ENABLED");
        MockHttpServletRequest request = new MockHttpServletRequest();
        MockHttpSession originalSession = (MockHttpSession) request.getSession(true);
        when(persistenceService.findByPhone("13800138000")).thenReturn(existing);
        org.mockito.Mockito.doThrow(new TransactionSystemException("simulated commit failure"))
                .when(persistenceService).recordSuccessfulLogin(7L);

        assertThatThrownBy(() -> service.login(
                loginRequest("13800138000", "right123"), request))
                .isInstanceOf(TransactionSystemException.class);

        assertThat(originalSession.isInvalid()).isFalse();
        assertThat(originalSession.getAttribute(GuitarAuthService.SESSION_ATTRIBUTE)).isNull();
        assertThat(request.getSession(false)).isSameAs(originalSession);
    }

    @Test
    void logoutInvalidatesExistingSessionAndCurrentSessionBecomesEmpty() {
        MockHttpServletRequest request = new MockHttpServletRequest();
        HttpSession session = request.getSession(true);
        session.setAttribute(GuitarAuthService.SESSION_ATTRIBUTE,
                new GuitarUserPrincipal(3L, "13800138000", "用户", null, "USER"));

        assertThat(authService.currentSession(request)).isPresent();
        authService.logout(request);

        assertThat(((MockHttpSession) session).isInvalid()).isTrue();
        assertThat(authService.currentSession(request)).isEmpty();
    }

    private RegisterRequest registerRequest(String phone, String password, String nickname) {
        RegisterRequest request = new RegisterRequest();
        request.setPhone(phone);
        request.setPassword(password);
        request.setNickname(nickname);
        return request;
    }

    private LoginRequest loginRequest(String phone, String password) {
        LoginRequest request = new LoginRequest();
        request.setPhone(phone);
        request.setPassword(password);
        return request;
    }

    private GuitarUser user(Long id, String phone, String passwordHash, String role, String status) {
        GuitarUser user = new GuitarUser();
        user.setId(id);
        user.setPhone(phone);
        user.setPasswordHash(passwordHash);
        user.setNickname("用户");
        user.setRole(role);
        user.setStatus(status);
        return user;
    }

    private String repeat(char value, int count) {
        StringBuilder result = new StringBuilder(count);
        for (int index = 0; index < count; index++) {
            result.append(value);
        }
        return result.toString();
    }

    private void assertRegisterSucceeds(String password, Long userId) {
        reset(guitarUserDao);
        when(guitarUserDao.findByPhone("13800138000")).thenReturn(null);
        doAnswer(invocation -> {
            GuitarUser inserted = invocation.getArgument(0);
            inserted.setId(userId);
            return 1;
        }).when(guitarUserDao).insert(any(GuitarUser.class));
        when(guitarUserDao.findById(userId)).thenAnswer(invocation -> {
            GuitarUser user = new GuitarUser();
            user.setId(userId);
            user.setPhone("13800138000");
            user.setNickname("用户");
            user.setRole("USER");
            return user;
        });

        GuitarUserPrincipal principal = authService.register(
                registerRequest("13800138000", password, "用户"), new MockHttpServletRequest());

        assertThat(principal.getId()).isEqualTo(userId);
    }

    private void assertApiError(ThrowingCallable callable, HttpStatus status, String code) {
        assertThatThrownBy(callable::call)
                .isInstanceOfSatisfying(GuitarApiException.class, exception -> {
                    assertThat(exception.getStatus()).isEqualTo(status);
                    assertThat(exception.getCode()).isEqualTo(code);
                });
    }

    @FunctionalInterface
    private interface ThrowingCallable {
        void call();
    }
}
