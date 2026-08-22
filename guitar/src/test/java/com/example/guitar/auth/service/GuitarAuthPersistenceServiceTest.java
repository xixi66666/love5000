package com.example.guitar.auth.service;

import com.example.guitar.user.dao.GuitarUserDao;
import com.example.guitar.web.GuitarApiException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class GuitarAuthPersistenceServiceTest {

    private GuitarUserDao guitarUserDao;
    private GuitarAuthPersistenceService persistenceService;

    @BeforeEach
    void setUp() {
        guitarUserDao = mock(GuitarUserDao.class);
        persistenceService = new GuitarAuthPersistenceService(guitarUserDao);
    }

    @Test
    void successfulLoginUpdateMustAffectExactlyOneUser() {
        when(guitarUserDao.updateLastLoginAt(eq(7L), any(LocalDateTime.class))).thenReturn(0);

        assertThatThrownBy(() -> persistenceService.recordSuccessfulLogin(7L))
                .isInstanceOfSatisfying(GuitarApiException.class, exception -> {
                    assertThat(exception.getStatus().value()).isEqualTo(500);
                    assertThat(exception.getCode()).isEqualTo("AUTH_STATE_UPDATE_FAILED");
                });
    }
}
