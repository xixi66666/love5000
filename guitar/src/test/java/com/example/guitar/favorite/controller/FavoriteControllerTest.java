package com.example.guitar.favorite.controller;

import com.example.guitar.auth.model.GuitarUserPrincipal;
import com.example.guitar.auth.service.GuitarAuthService;
import com.example.guitar.auth.web.CsrfTokenService;
import com.example.guitar.favorite.service.FavoriteService;
import com.example.guitar.favorite.vo.FavoriteFolderResponse;
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
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
class FavoriteControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private CsrfTokenService csrfTokenService;

    @MockBean
    private FavoriteService favoriteService;

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
    void exposesFolderListAndPublishedSheetListUsingOnlySessionUserId() throws Exception {
        MockHttpSession session = session();
        FavoriteFolderResponse folder = new FavoriteFolderResponse(12L, "练习", 3, null, null);
        when(favoriteService.listFolders(7L)).thenReturn(Collections.singletonList(folder));
        when(favoriteService.listSheets(7L, 12L)).thenReturn(Collections.emptyList());

        mockMvc.perform(get("/api/favorite-folders").session(session))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data[0].id").value(12))
                .andExpect(jsonPath("$.data[0].name").value("练习"))
                .andExpect(jsonPath("$.data[0].userId").doesNotExist());

        mockMvc.perform(get("/api/favorite-folders/12/sheets").session(session))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true));

        verify(favoriteService).listFolders(7L);
        verify(favoriteService).listSheets(7L, 12L);
    }

    @Test
    void exposesCreateUpdateAndDeleteWithCsrfAndIgnoresClientUserId() throws Exception {
        MockHttpSession session = session();
        String token = token(session);
        FavoriteFolderResponse created = new FavoriteFolderResponse(12L, "练习", 0, null, null);
        FavoriteFolderResponse updated = new FavoriteFolderResponse(12L, "演出", 2, null, null);
        when(favoriteService.createFolder(eq(7L), any())).thenReturn(created);
        when(favoriteService.updateFolder(eq(7L), eq(12L), any())).thenReturn(updated);

        mockMvc.perform(post("/api/favorite-folders")
                        .session(session).header(CsrfTokenService.HEADER_NAME, token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"userId\":999,\"name\":\"练习\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.id").value(12));

        mockMvc.perform(put("/api/favorite-folders/12")
                        .session(session).header(CsrfTokenService.HEADER_NAME, token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"userId\":999,\"name\":\"演出\",\"sortOrder\":2}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.name").value("演出"));

        mockMvc.perform(delete("/api/favorite-folders/12")
                        .session(session).header(CsrfTokenService.HEADER_NAME, token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true));

        verify(favoriteService).deleteFolder(7L, 12L);
    }

    @Test
    void exposesAddAndIdempotentRemoveWithCsrf() throws Exception {
        MockHttpSession session = session();
        String token = token(session);

        mockMvc.perform(post("/api/favorite-folders/12/sheets/99")
                        .session(session).header(CsrfTokenService.HEADER_NAME, token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true));

        mockMvc.perform(delete("/api/favorite-folders/12/sheets/99")
                        .session(session).header(CsrfTokenService.HEADER_NAME, token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true));

        verify(favoriteService).addFavorite(7L, 12L, 99L);
        verify(favoriteService).removeFavorite(7L, 12L, 99L);

        mockMvc.perform(post("/api/favorite-folders/12/sheets/99").session(session))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("CSRF_INVALID"));
    }

    private MockHttpSession session() {
        MockHttpSession session = new MockHttpSession();
        session.setAttribute(GuitarAuthService.SESSION_ATTRIBUTE,
                new GuitarUserPrincipal(7L, "13800138000", "tester", null, "USER"));
        csrfTokenService.getOrCreateToken(session);
        return session;
    }

    private String token(MockHttpSession session) {
        return (String) session.getAttribute(CsrfTokenService.SESSION_ATTRIBUTE);
    }
}
