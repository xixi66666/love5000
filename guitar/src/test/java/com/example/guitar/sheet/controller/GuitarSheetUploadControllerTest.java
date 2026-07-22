package com.example.guitar.sheet.controller;

import com.example.guitar.auth.model.GuitarUserPrincipal;
import com.example.guitar.auth.service.GuitarAuthService;
import com.example.guitar.auth.web.CsrfTokenService;
import com.example.guitar.auth.web.GuitarAuthInterceptor;
import com.example.guitar.sheet.service.GuitarSheetService;
import com.example.guitar.sheet.vo.SheetDetailResponse;
import com.example.guitar.web.ApiExceptionHandler;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockHttpSession;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.mock.web.MockPart;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockMultipartHttpServletRequestBuilder;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.util.Optional;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class GuitarSheetUploadControllerTest {

    private GuitarSheetService sheetService;
    private GuitarAuthService authService;
    private CsrfTokenService csrfTokenService;
    private MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        sheetService = mock(GuitarSheetService.class);
        authService = mock(GuitarAuthService.class);
        csrfTokenService = new CsrfTokenService();
        mockMvc = MockMvcBuilders.standaloneSetup(new GuitarSheetController(sheetService, authService))
                .setControllerAdvice(new ApiExceptionHandler())
                .addInterceptors(new GuitarAuthInterceptor(authService, csrfTokenService))
                .build();
    }

    @Test
    void authenticatedMultipartUploadRequiresCsrfAndPassesOnlySessionUserToService() throws Exception {
        MockHttpSession session = new MockHttpSession();
        String csrfToken = csrfTokenService.getOrCreateToken(session);
        GuitarUserPrincipal principal = new GuitarUserPrincipal(8L, "13800138000", "Uploader", null, "USER");
        when(authService.currentSession(any())).thenReturn(Optional.of(principal));
        SheetDetailResponse response = new SheetDetailResponse();
        response.setId(12L);
        when(sheetService.createSheet(any(), any(), any(), any())).thenReturn(response);

        mockMvc.perform(uploadRequest().session(session).header(CsrfTokenService.HEADER_NAME, csrfToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.id").value(12));
        verify(sheetService).createSheet(org.mockito.ArgumentMatchers.eq(8L),
                org.mockito.ArgumentMatchers.eq("Uploader"), any(), any());
    }

    @Test
    void uploadRejectsMissingCsrfBeforeControllerOrService() throws Exception {
        mockMvc.perform(uploadRequest())
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.code").value("CSRF_INVALID"));
    }

    @Test
    void validCsrfWithoutSessionUserReturnsJsonUnauthorized() throws Exception {
        MockHttpSession session = new MockHttpSession();
        when(authService.currentSession(any())).thenReturn(Optional.empty());

        mockMvc.perform(uploadRequest().session(session)
                        .header(CsrfTokenService.HEADER_NAME, csrfTokenService.getOrCreateToken(session)))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.code").value("AUTH_REQUIRED"));
    }

    private MockMultipartHttpServletRequestBuilder uploadRequest() {
        MockPart metadata = new MockPart("metadata", ("{\"songName\":\"Song\",\"singer\":\"Singer\","
                + "\"sheetType\":\"TAB\",\"difficulty\":\"BEGINNER\",\"keySignature\":\"C\","
                + "\"tuning\":\"Standard\",\"fileMode\":\"PDF\"}")
                .getBytes(java.nio.charset.StandardCharsets.UTF_8));
        metadata.getHeaders().setContentType(MediaType.APPLICATION_JSON);
        return org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart("/api/sheets")
                .part(metadata)
                .file(new MockMultipartFile("files", "song.pdf", "application/pdf",
                        "%PDF-1.7".getBytes(java.nio.charset.StandardCharsets.US_ASCII)));
    }
}
