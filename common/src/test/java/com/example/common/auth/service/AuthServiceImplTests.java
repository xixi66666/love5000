package com.example.common.auth.service;

import com.example.common.auth.config.AuthProperties;
import com.example.common.auth.dto.AuthRequest;
import com.example.common.auth.exception.AuthException;
import com.example.common.auth.model.AuthUser;
import com.example.common.auth.model.AuthUserPrincipal;
import com.example.common.auth.repository.AuthUserRepository;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;

import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class AuthServiceImplTests {

    @Test
    void shouldHashPasswordAndMatch() {
        AuthPasswordService passwordService = new AuthPasswordService();

        String hash = passwordService.hash("password123");

        assertNotEquals("password123", hash);
        assertTrue(passwordService.matches("password123", hash));
    }

    @Test
    void shouldRegisterAndSaveSession() {
        FakeAuthUserRepository repository = new FakeAuthUserRepository();
        AuthServiceImpl service = new AuthServiceImpl(repository, new AuthPasswordService(), new AuthProperties());
        MockHttpServletRequest request = new MockHttpServletRequest();
        AuthRequest authRequest = new AuthRequest();
        authRequest.setUsername("Caleb_01");
        authRequest.setPassword("password123");
        authRequest.setDisplayName("Caleb");

        AuthUserPrincipal principal = service.register(authRequest, request);

        assertNotNull(principal.getId());
        assertEquals("caleb_01", principal.getUsername());
        assertTrue(service.currentUser(request).isPresent());
    }

    @Test
    void shouldRejectWrongPassword() {
        FakeAuthUserRepository repository = new FakeAuthUserRepository();
        AuthPasswordService passwordService = new AuthPasswordService();
        repository.save("caleb", passwordService.hash("password123"), "Caleb", "USER");
        AuthServiceImpl service = new AuthServiceImpl(repository, passwordService, new AuthProperties());
        AuthRequest authRequest = new AuthRequest();
        authRequest.setUsername("caleb");
        authRequest.setPassword("wrong-password");

        assertThrows(AuthException.class, () -> service.login(authRequest, new MockHttpServletRequest()));
    }

    @Test
    void shouldRejectInvalidRegistrationInputWithDetails() {
        AuthServiceImpl service = new AuthServiceImpl(new FakeAuthUserRepository(), new AuthPasswordService(), new AuthProperties());
        AuthRequest badUsernameRequest = new AuthRequest();
        badUsernameRequest.setUsername("bad name");
        badUsernameRequest.setPassword("password123");

        AuthException usernameException = assertThrows(AuthException.class,
                () -> service.register(badUsernameRequest, new MockHttpServletRequest()));
        assertEquals("USERNAME_INVALID", usernameException.getCode());
        assertTrue(usernameException.getDetails().size() >= 3);

        AuthRequest badPasswordRequest = new AuthRequest();
        badPasswordRequest.setUsername("xixi");
        badPasswordRequest.setPassword("password");

        AuthException passwordException = assertThrows(AuthException.class,
                () -> service.register(badPasswordRequest, new MockHttpServletRequest()));
        assertEquals("PASSWORD_INVALID", passwordException.getCode());
        assertTrue(passwordException.getDetails().size() >= 4);
    }

    private static class FakeAuthUserRepository implements AuthUserRepository {

        private final Map<Long, AuthUser> users = new HashMap<Long, AuthUser>();

        private long nextId = 1L;

        @Override
        public Optional<AuthUser> findByUsername(String username) {
            for (AuthUser user : users.values()) {
                if (user.getUsername().equals(username)) {
                    return Optional.of(user);
                }
            }
            return Optional.empty();
        }

        @Override
        public Optional<AuthUser> findById(Long id) {
            return Optional.ofNullable(users.get(id));
        }

        @Override
        public Long save(String username, String passwordHash, String displayName, String role) {
            AuthUser user = new AuthUser();
            user.setId(nextId++);
            user.setUsername(username);
            user.setDisplayName(displayName);
            user.setPasswordHash(passwordHash);
            user.setRole(role);
            user.setEnabled(true);
            users.put(user.getId(), user);
            return user.getId();
        }
    }
}
