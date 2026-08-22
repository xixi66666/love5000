package com.example.guitar.auth.controller;

import com.example.guitar.auth.model.GuitarUserPrincipal;
import com.example.guitar.auth.service.GuitarAuthService;
import com.example.guitar.auth.web.CsrfTokenService;
import com.example.guitar.auth.web.GuitarAuthInterceptor;
import com.example.guitar.web.ApiExceptionHandler;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockHttpSession;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.util.Optional;

import static org.hamcrest.Matchers.nullValue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class GuitarAuthControllerTest {

    private GuitarAuthService authService;
    private MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        authService = mock(GuitarAuthService.class);
        CsrfTokenService csrfTokenService = new CsrfTokenService();
        GuitarAuthController controller = new GuitarAuthController(authService, csrfTokenService);
        mockMvc = MockMvcBuilders.standaloneSetup(controller)
                .setControllerAdvice(new ApiExceptionHandler())
                .addInterceptors(new GuitarAuthInterceptor(authService, csrfTokenService))
                .build();
        when(authService.currentSession(any())).thenReturn(Optional.empty());
    }

    @Test
    void registerReturnsSuccessfulEnvelope() throws Exception {
        GuitarUserPrincipal principal = principal("USER");
        when(authService.register(any(), any())).thenReturn(principal);
        SessionToken sessionToken = createSessionToken();

        mockMvc.perform(post("/api/auth/register")
                        .session(sessionToken.session)
                        .header(CsrfTokenService.HEADER_NAME, sessionToken.token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"phone\":\"13800138000\",\"password\":\"guitar123\",\"nickname\":\"旋律\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.id").value(8))
                .andExpect(jsonPath("$.data.phone").value("13800138000"));
    }

    @Test
    void invalidRegisterReturnsBadRequestContract() throws Exception {
        when(authService.register(any(), any())).thenThrow(
                new com.example.guitar.web.GuitarApiException(
                        org.springframework.http.HttpStatus.BAD_REQUEST,
                        "PHONE_INVALID",
                        "手机号格式不正确"));
        SessionToken sessionToken = createSessionToken();

        mockMvc.perform(post("/api/auth/register")
                        .session(sessionToken.session)
                        .header(CsrfTokenService.HEADER_NAME, sessionToken.token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"phone\":\"123\",\"password\":\"guitar123\",\"nickname\":\"旋律\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.code").value("PHONE_INVALID"))
                .andExpect(jsonPath("$.message").isNotEmpty());
    }

    @Test
    void failedLoginReturnsUnauthorizedContract() throws Exception {
        when(authService.login(any(), any())).thenThrow(
                new com.example.guitar.web.GuitarApiException(
                        org.springframework.http.HttpStatus.UNAUTHORIZED,
                        "AUTH_FAILED",
                        "手机号或密码错误"));
        SessionToken sessionToken = createSessionToken();

        mockMvc.perform(post("/api/auth/login")
                        .session(sessionToken.session)
                        .header(CsrfTokenService.HEADER_NAME, sessionToken.token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"phone\":\"13800138000\",\"password\":\"wrong123\"}"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.code").value("AUTH_FAILED"));
    }

    @Test
    void authWriteRejectsMissingCsrfToken() throws Exception {
        mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"phone\":\"13800138000\",\"password\":\"guitar123\"}"))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.code").value("CSRF_INVALID"));
    }

    @Test
    void sessionResponseIncludesCurrentUserAndCsrfToken() throws Exception {
        when(authService.currentSession(any())).thenReturn(Optional.of(principal("USER")));

        mockMvc.perform(get("/api/auth/session"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.user.id").value(8))
                .andExpect(jsonPath("$.data.csrfToken").isNotEmpty());
    }

    @Test
    void sessionResponseIncludesExplicitNullForAnonymousUser() throws Exception {
        mockMvc.perform(get("/api/auth/session"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.user").value(nullValue()))
                .andExpect(jsonPath("$.data.csrfToken").isNotEmpty());
    }

    @Test
    void malformedJsonReturnsValidationEnvelope() throws Exception {
        SessionToken sessionToken = createSessionToken();

        mockMvc.perform(post("/api/auth/register")
                        .session(sessionToken.session)
                        .header(CsrfTokenService.HEADER_NAME, sessionToken.token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{not-json}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.code").value("VALIDATION_ERROR"));
    }

    @Test
    void logoutReturnsSuccessfulEnvelope() throws Exception {
        SessionToken sessionToken = createSessionToken();

        mockMvc.perform(post("/api/auth/logout")
                        .session(sessionToken.session)
                        .header(CsrfTokenService.HEADER_NAME, sessionToken.token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true));
    }

    private SessionToken createSessionToken() throws Exception {
        MvcResult result = mockMvc.perform(get("/api/auth/session"))
                .andExpect(status().isOk())
                .andReturn();
        MockHttpSession session = (MockHttpSession) result.getRequest().getSession(false);
        String token = (String) session.getAttribute(CsrfTokenService.SESSION_ATTRIBUTE);
        return new SessionToken(session, token);
    }

    private GuitarUserPrincipal principal(String role) {
        return new GuitarUserPrincipal(8L, "13800138000", "旋律", null, role);
    }

    private static class SessionToken {
        private final MockHttpSession session;
        private final String token;

        private SessionToken(MockHttpSession session, String token) {
            this.session = session;
            this.token = token;
        }
    }
}
