package com.example.guitar.user.controller;

import com.example.guitar.auth.model.GuitarUserPrincipal;
import com.example.guitar.auth.service.GuitarAuthService;
import com.example.guitar.auth.web.CsrfTokenService;
import com.example.guitar.user.service.GuitarUserService;
import com.example.guitar.web.GuitarApiException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockHttpSession;
import org.springframework.test.web.servlet.MockMvc;

import javax.servlet.http.HttpServletRequest;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
class GuitarUserControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private CsrfTokenService csrfTokenService;

    @MockBean
    private GuitarUserService guitarUserService;

    @MockBean
    private GuitarAuthService guitarAuthService;

    @BeforeEach
    void setUp() {
        when(guitarAuthService.currentSession(any(HttpServletRequest.class))).thenAnswer(invocation -> {
            HttpServletRequest request = invocation.getArgument(0);
            Object principal = request.getSession(false) == null ? null
                    : request.getSession(false).getAttribute(GuitarAuthService.SESSION_ATTRIBUTE);
            return principal instanceof GuitarUserPrincipal
                    ? Optional.of((GuitarUserPrincipal) principal) : Optional.empty();
        });
    }

    @Test
    void profileUpdateUsesConfiguredInterceptorCsrfAndAuthenticatedSessionOwner() throws Exception {
        GuitarUserPrincipal current = principal(8L, "old", null);
        GuitarUserPrincipal updated = principal(8L, "new", null);
        MockHttpSession session = session(current);
        String csrfToken = token(session);
        when(guitarUserService.updateNickname(8L, "new")).thenReturn(updated);

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
        assertThat(session.getAttribute(GuitarAuthService.SESSION_ATTRIBUTE)).isSameAs(updated);
        assertThat(token(session)).isEqualTo(csrfToken);

        mockMvc.perform(put("/api/users/me")
                        .session(session)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"nickname\":\"ignored\"}"))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("CSRF_INVALID"));
    }

    @Test
    void avatarUploadUsesConfiguredInterceptorCsrfAndAuthenticatedSessionOwner() throws Exception {
        GuitarUserPrincipal current = principal(8L, "old", null);
        GuitarUserPrincipal updated = principal(8L, "old", "new/avatar.png");
        MockHttpSession session = session(current);
        when(guitarUserService.updateAvatar(eq(8L), any())).thenReturn(updated);

        mockMvc.perform(multipart("/api/users/me/avatar")
                        .file("avatar", new byte[]{(byte) 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A})
                        .session(session)
                        .header(CsrfTokenService.HEADER_NAME, token(session)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.id").value(8))
                .andExpect(jsonPath("$.data.avatarObjectKey").value("new/avatar.png"));

        verify(guitarUserService).updateAvatar(eq(8L), any());
        assertThat(session.getAttribute(GuitarAuthService.SESSION_ATTRIBUTE)).isSameAs(updated);

        mockMvc.perform(multipart("/api/users/me/avatar")
                        .file("avatar", new byte[]{1})
                        .session(session))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("CSRF_INVALID"));
    }

    @Test
    void persistenceUpdateOrReloadFailureKeepsSessionPrincipalAndCsrfToken() throws Exception {
        GuitarUserPrincipal current = principal(8L, "old", "old/avatar.png");
        MockHttpSession session = session(current);
        String csrfToken = token(session);
        when(guitarUserService.updateNickname(8L, "new")).thenThrow(new GuitarApiException(
                HttpStatus.INTERNAL_SERVER_ERROR, "PROFILE_UPDATE_FAILED", "failed"));

        mockMvc.perform(put("/api/users/me")
                        .session(session)
                        .header(CsrfTokenService.HEADER_NAME, csrfToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"nickname\":\"new\"}"))
                .andExpect(status().isInternalServerError())
                .andExpect(jsonPath("$.code").value("PROFILE_UPDATE_FAILED"));

        assertThat(session.getAttribute(GuitarAuthService.SESSION_ATTRIBUTE)).isSameAs(current);
        assertThat(token(session)).isEqualTo(csrfToken);
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
