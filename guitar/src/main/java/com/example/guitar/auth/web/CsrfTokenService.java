package com.example.guitar.auth.web;

import org.springframework.stereotype.Service;

import javax.servlet.http.HttpSession;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.Base64;

@Service
public class CsrfTokenService {

    public static final String HEADER_NAME = "X-CSRF-Token";
    public static final String SESSION_ATTRIBUTE = "GUITAR_CSRF_TOKEN";

    private static final int TOKEN_BYTES = 32;

    private final SecureRandom secureRandom;

    public CsrfTokenService() {
        this(new SecureRandom());
    }

    CsrfTokenService(SecureRandom secureRandom) {
        this.secureRandom = secureRandom;
    }

    public String getOrCreateToken(HttpSession session) {
        Object existing = session.getAttribute(SESSION_ATTRIBUTE);
        if (existing instanceof String && !((String) existing).isEmpty()) {
            return (String) existing;
        }
        byte[] randomBytes = new byte[TOKEN_BYTES];
        secureRandom.nextBytes(randomBytes);
        String token = Base64.getUrlEncoder().withoutPadding().encodeToString(randomBytes);
        session.setAttribute(SESSION_ATTRIBUTE, token);
        return token;
    }

    public boolean isValid(HttpSession session, String submittedToken) {
        if (session == null || submittedToken == null || submittedToken.isEmpty()) {
            return false;
        }
        Object expected = session.getAttribute(SESSION_ATTRIBUTE);
        if (!(expected instanceof String)) {
            return false;
        }
        byte[] expectedBytes = ((String) expected).getBytes(StandardCharsets.UTF_8);
        byte[] submittedBytes = submittedToken.getBytes(StandardCharsets.UTF_8);
        return MessageDigest.isEqual(expectedBytes, submittedBytes);
    }
}
