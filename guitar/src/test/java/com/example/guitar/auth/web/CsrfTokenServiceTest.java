package com.example.guitar.auth.web;

import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpSession;

import java.util.Base64;

import static org.assertj.core.api.Assertions.assertThat;

class CsrfTokenServiceTest {

    private final CsrfTokenService csrfTokenService = new CsrfTokenService();

    @Test
    void generatedTokenContainsThirtyTwoRandomBytesAndIsReusedBySession() {
        MockHttpSession session = new MockHttpSession();

        String token = csrfTokenService.getOrCreateToken(session);

        assertThat(Base64.getUrlDecoder().decode(token)).hasSize(32);
        assertThat(token).doesNotContain("=");
        assertThat(csrfTokenService.getOrCreateToken(session)).isEqualTo(token);
    }

    @Test
    void validationAcceptsExactTokenAndRejectsMissingOrDifferentToken() {
        MockHttpSession session = new MockHttpSession();
        String token = csrfTokenService.getOrCreateToken(session);

        assertThat(csrfTokenService.isValid(session, token)).isTrue();
        assertThat(csrfTokenService.isValid(session, token + "x")).isFalse();
        assertThat(csrfTokenService.isValid(session, null)).isFalse();
        assertThat(csrfTokenService.isValid(null, token)).isFalse();
    }
}
