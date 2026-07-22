package com.example.guitar.admin.controller;

import com.example.guitar.admin.dto.AdminSheetSearchRequest;
import com.example.guitar.admin.service.SheetAdminService;
import com.example.guitar.admin.vo.AdminSheetSummaryResponse;
import com.example.guitar.auth.model.GuitarUserPrincipal;
import com.example.guitar.auth.service.GuitarAuthService;
import com.example.guitar.auth.web.CsrfTokenService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockHttpSession;
import org.springframework.test.web.servlet.MockMvc;

import javax.servlet.http.HttpServletRequest;
import java.util.Collections;
import java.util.Optional;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
class SheetAdminControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private CsrfTokenService csrfTokenService;

    @MockBean
    private SheetAdminService sheetAdminService;

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
    void adminCanListSheetsWithApprovedQueryParameters() throws Exception {
        SheetAdminService.AdminSheetSearchResult result = new SheetAdminService.AdminSheetSearchResult(
                Collections.singletonList(summary(101L, "OFFLINE")), 1, 2, 10);
        when(sheetAdminService.list(any(AdminSheetSearchRequest.class))).thenReturn(result);

        mockMvc.perform(get("/api/admin/sheets")
                        .session(session("ADMIN"))
                        .param("status", "OFFLINE")
                        .param("sort", "LATEST")
                        .param("page", "2")
                        .param("size", "10"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.total").value(1))
                .andExpect(jsonPath("$.data.page").value(2))
                .andExpect(jsonPath("$.data.records[0].status").value("OFFLINE"));

        verify(sheetAdminService).list(any(AdminSheetSearchRequest.class));
    }

    @Test
    void ordinaryUserReceivesForbiddenForEveryAdminApi() throws Exception {
        MockHttpSession session = session("USER");
        String token = token(session);

        mockMvc.perform(get("/api/admin/sheets").session(session))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.code").value("ADMIN_REQUIRED"));

        mockMvc.perform(post("/api/admin/sheets/101/offline")
                        .session(session).header(CsrfTokenService.HEADER_NAME, token)
                        .contentType(MediaType.APPLICATION_JSON).content("{\"reason\":\"违规\"}"))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("ADMIN_REQUIRED"));

        mockMvc.perform(post("/api/admin/sheets/101/restore")
                        .session(session).header(CsrfTokenService.HEADER_NAME, token))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("ADMIN_REQUIRED"));
    }

    @Test
    void offlineUsesSessionAdminAndContainerRemoteAddressInsteadOfClientFieldsOrForwardedHeader() throws Exception {
        MockHttpSession session = session("ADMIN");
        String token = token(session);
        when(sheetAdminService.offline(7L, 101L, "版权整改", "10.0.0.8"))
                .thenReturn(summary(101L, "OFFLINE"));

        mockMvc.perform(post("/api/admin/sheets/101/offline")
                        .with(request -> {
                            request.setRemoteAddr("10.0.0.8");
                            return request;
                        })
                        .session(session)
                        .header(CsrfTokenService.HEADER_NAME, token)
                        .header("X-Forwarded-For", "203.0.113.99")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"reason\":\"版权整改\",\"adminUserId\":999,\"role\":\"USER\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.status").value("OFFLINE"));

        verify(sheetAdminService).offline(7L, 101L, "版权整改", "10.0.0.8");
    }

    @Test
    void restoreUsesSessionAdminAndRequiresCsrf() throws Exception {
        MockHttpSession session = session("ADMIN");
        String token = token(session);
        when(sheetAdminService.restore(eq(7L), eq(101L), any(String.class)))
                .thenReturn(summary(101L, "PUBLISHED"));

        mockMvc.perform(post("/api/admin/sheets/101/restore")
                        .session(session).header(CsrfTokenService.HEADER_NAME, token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.status").value("PUBLISHED"));

        mockMvc.perform(post("/api/admin/sheets/101/restore").session(session))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("CSRF_INVALID"));
    }

    private MockHttpSession session(String role) {
        MockHttpSession session = new MockHttpSession();
        session.setAttribute(GuitarAuthService.SESSION_ATTRIBUTE,
                new GuitarUserPrincipal(7L, "13800138000", "管理员", null, role));
        csrfTokenService.getOrCreateToken(session);
        return session;
    }

    private String token(MockHttpSession session) {
        return (String) session.getAttribute(CsrfTokenService.SESSION_ATTRIBUTE);
    }

    private AdminSheetSummaryResponse summary(long id, String status) {
        AdminSheetSummaryResponse response = new AdminSheetSummaryResponse();
        response.setId(id);
        response.setStatus(status);
        return response;
    }
}
