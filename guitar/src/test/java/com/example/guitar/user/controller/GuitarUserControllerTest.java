package com.example.guitar.user.controller;

import com.example.guitar.auth.model.GuitarUserPrincipal;
import com.example.guitar.auth.service.GuitarAuthService;
import com.example.guitar.auth.web.CsrfTokenService;
import com.example.guitar.auth.web.GuitarAuthInterceptor;
import com.example.guitar.user.service.GuitarUserService;
import com.example.guitar.web.ApiExceptionHandler;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockHttpSession;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.util.Optional;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class GuitarUserControllerTest {

    private GuitarUserService guitarUserService;
    private GuitarAuthService guitarAuthService;
    private CsrfTokenService csrfTokenService;
    private MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        guitarUserService = mock(GuitarUserService.class);
        guitarAuthService = mock(GuitarAuthService.class);
        csrfTokenService = new CsrfTokenService();
        mockMvc = MockMvcBuilders.standaloneSetup(new GuitarUserController(guitarUserService, guitarAuthService))
                .setControllerAdvice(new ApiExceptionHandler())
                .addInterceptors(new GuitarAuthInterceptor(guitarAuthService, csrfTokenService))
                .build();
    }

    @Test
    void profileUpdateUsesAuthenticatedSessionOwnerAndRefreshesExistingPrincipal() throws Exception {
        GuitarUserPrincipal current = principal(8L, "old", null);
        GuitarUserPrincipal updated = principal(8L, "new", null);
        MockHttpSession session = session(current);
        when(guitarAuthService.currentSession(any())).thenReturn(Optional.of(current));
        when(guitarUserService.updateNickname(8L, "new")).thenReturn(updated);
        String csrfToken = token(session);

        mockMvc.perform(put("/api/users/me")
                        .session(session)
                        .header(CsrfTokenService.HEADER_NAME, csrfToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"userId\":999,\"nickname\":\"new\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.id").value(8))
                .andExpect(jsonPath("$.data.nickname").value("new"));

        verify(guitarUserService).updateNickname(8L, "new");
        org.assertj.core.api.Assertions.assertThat(session.getAttribute(GuitarAuthService.SESSION_ATTRIBUTE))
                .isSameAs(updated);
        org.assertj.core.api.Assertions.assertThat(token(session)).isEqualTo(csrfToken);
    }

    @Test
    void avatarUploadUsesAuthenticatedSessionOwnerAndRequiresCsrfToken() throws Exception {
        GuitarUserPrincipal current = principal(8L, "old", null);
        GuitarUserPrincipal updated = principal(8L, "old", "new/avatar.png");
        MockHttpSession session = session(current);
        when(guitarAuthService.currentSession(any())).thenReturn(Optional.of(current));
        when(guitarUserService.updateAvatar(eq(8L), any())).thenReturn(updated);

        mockMvc.perform(multipart("/api/users/me/avatar")
                        .file("avatar", new byte[]{(byte) 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A})
                        .session(session)
                        .header(CsrfTokenService.HEADER_NAME, token(session)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.id").value(8))
                .andExpect(jsonPath("$.data.avatarObjectKey").value("new/avatar.png"));
        verify(guitarUserService).updateAvatar(eq(8L), any());

        mockMvc.perform(multipart("/api/users/me/avatar")
                        .file("avatar", new byte[]{1})
                        .session(session))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("CSRF_INVALID"));
    }

    @Test
    void anonymousProfileRequestReturnsJsonUnauthorizedResponse() throws Exception {
        when(guitarAuthService.currentSession(any())).thenReturn(Optional.empty());

        mockMvc.perform(put("/api/users/me")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"nickname\":\"new\"}"))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("CSRF_INVALID"));
    }

    private MockHttpSession session(GuitarUserPrincipal principal) {
        MockHttpSession session = new MockHttpSession();
        session.setAttribute(GuitarAuthService.SESSION_ATTRIBUTE, principal);
        csrfTokenService.getOrCreateToken(session);
        return session;
    }

    private String token(MockHttpSession session) {
        return (String) session.getAttribute(CsrfTokenService.SESSION_ATTRIBUTE);
    }

    private GuitarUserPrincipal principal(Long id, String nickname, String avatarObjectKey) {
        return new GuitarUserPrincipal(id, "13800138000", nickname, avatarObjectKey, "USER");
    }
}
