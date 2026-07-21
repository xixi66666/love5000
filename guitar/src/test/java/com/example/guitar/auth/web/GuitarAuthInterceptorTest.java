package com.example.guitar.auth.web;

import com.example.guitar.auth.model.GuitarUserPrincipal;
import com.example.guitar.auth.service.GuitarAuthService;
import com.example.guitar.web.ApiExceptionHandler;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpSession;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestMethod;
import org.springframework.web.bind.annotation.RestController;

import java.util.Collections;
import java.util.Map;
import java.util.Optional;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class GuitarAuthInterceptorTest {

    private GuitarAuthService authService;
    private CsrfTokenService csrfTokenService;
    private MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        authService = mock(GuitarAuthService.class);
        csrfTokenService = new CsrfTokenService();
        mockMvc = MockMvcBuilders.standaloneSetup(new ProtectedTestController())
                .setControllerAdvice(new ApiExceptionHandler())
                .addInterceptors(new GuitarAuthInterceptor(authService, csrfTokenService))
                .build();
        when(authService.currentSession(any())).thenReturn(Optional.empty());
    }

    @Test
    void writeRequestRejectsMissingCsrfToken() throws Exception {
        mockMvc.perform(post("/api/public"))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("CSRF_INVALID"));
    }

    @Test
    void putPatchAndDeleteAlsoRejectMissingCsrfToken() throws Exception {
        mockMvc.perform(put("/api/public"))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("CSRF_INVALID"));
        mockMvc.perform(patch("/api/public"))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("CSRF_INVALID"));
        mockMvc.perform(delete("/api/public"))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("CSRF_INVALID"));
    }

    @Test
    void writeRequestRejectsBadCsrfToken() throws Exception {
        MockHttpSession session = sessionWithCsrfToken();

        mockMvc.perform(post("/api/public")
                        .session(session)
                        .header(CsrfTokenService.HEADER_NAME, "bad-token"))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("CSRF_INVALID"));
    }

    @Test
    void writeRequestAcceptsMatchingCsrfToken() throws Exception {
        MockHttpSession session = sessionWithCsrfToken();

        mockMvc.perform(post("/api/public")
                        .session(session)
                        .header(CsrfTokenService.HEADER_NAME, token(session)))
                .andExpect(status().isOk());
    }

    @Test
    void anonymousUserCannotAccessProtectedEndpoint() throws Exception {
        mockMvc.perform(get("/api/users/me"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("AUTH_REQUIRED"));
    }

    @Test
    void regularUserCannotAccessAdminEndpoint() throws Exception {
        MockHttpSession session = sessionWithCsrfToken();
        when(authService.currentSession(any())).thenReturn(Optional.of(principal("USER")));

        mockMvc.perform(post("/api/admin/stats")
                        .session(session)
                        .header(CsrfTokenService.HEADER_NAME, token(session)))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("ADMIN_REQUIRED"));
    }

    @Test
    void administratorCanAccessAdminEndpoint() throws Exception {
        MockHttpSession session = sessionWithCsrfToken();
        when(authService.currentSession(any())).thenReturn(Optional.of(principal("ADMIN")));

        mockMvc.perform(post("/api/admin/stats")
                        .session(session)
                        .header(CsrfTokenService.HEADER_NAME, token(session)))
                .andExpect(status().isOk());
    }

    @Test
    void anonymousCannotWriteSheetsEvenWithValidCsrfToken() throws Exception {
        MockHttpSession session = sessionWithCsrfToken();

        mockMvc.perform(post("/api/sheets/upload")
                        .session(session)
                        .header(CsrfTokenService.HEADER_NAME, token(session)))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("AUTH_REQUIRED"));
    }

    @Test
    void publicGetIsAllowedWithoutSession() throws Exception {
        mockMvc.perform(get("/api/public"))
                .andExpect(status().isOk());
    }

    private MockHttpSession sessionWithCsrfToken() {
        MockHttpSession session = new MockHttpSession();
        csrfTokenService.getOrCreateToken(session);
        return session;
    }

    private String token(MockHttpSession session) {
        return (String) session.getAttribute(CsrfTokenService.SESSION_ATTRIBUTE);
    }

    private GuitarUserPrincipal principal(String role) {
        return new GuitarUserPrincipal(8L, "13800138000", "旋律", null, role);
    }

    @RestController
    private static class ProtectedTestController {

        @RequestMapping(value = "/api/public", method = {RequestMethod.GET, RequestMethod.POST,
                RequestMethod.PUT, RequestMethod.PATCH, RequestMethod.DELETE})
        public Map<String, Object> publicEndpoint() {
            return Collections.<String, Object>singletonMap("success", true);
        }

        @GetMapping("/api/users/me")
        public Map<String, Object> userEndpoint() {
            return Collections.<String, Object>singletonMap("success", true);
        }

        @PostMapping("/api/sheets/upload")
        public Map<String, Object> sheetEndpoint() {
            return Collections.<String, Object>singletonMap("success", true);
        }

        @PostMapping("/api/admin/stats")
        public Map<String, Object> adminEndpoint() {
            return Collections.<String, Object>singletonMap("success", true);
        }
    }
}
