package com.example.guitar.sheet.controller;

import com.example.guitar.sheet.service.GuitarSheetService;
import com.example.guitar.sheet.vo.SheetDetailResponse;
import com.example.guitar.sheet.vo.SheetSummaryResponse;
import com.example.guitar.web.GuitarApiException;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.HttpStatus;
import org.springframework.test.web.servlet.MockMvc;

import java.util.Collections;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
class GuitarSheetControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private GuitarSheetService guitarSheetService;

    @Test
    void anonymousUserCanSearchPublicSheetsAndReceivesPaginationEnvelope() throws Exception {
        SheetSummaryResponse record = new SheetSummaryResponse();
        record.setId(9L);
        record.setSongName("Song");
        when(guitarSheetService.searchPublicSheets(any())).thenReturn(
                new GuitarSheetService.SheetSearchResult(Collections.singletonList(record), 1L, 1, 20));

        mockMvc.perform(get("/api/sheets").param("page", "1").param("size", "20"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.total").value(1))
                .andExpect(jsonPath("$.data.records[0].id").value(9));
    }

    @Test
    void anonymousUserCanReadPublishedDetailWhileMissingSheetUsesSanitizedError() throws Exception {
        SheetDetailResponse detail = new SheetDetailResponse();
        detail.setId(9L);
        when(guitarSheetService.getPublicSheetDetail(9L)).thenReturn(detail);
        when(guitarSheetService.getPublicSheetDetail(10L)).thenThrow(new GuitarApiException(
                HttpStatus.NOT_FOUND, "SHEET_NOT_FOUND", "曲谱不存在或不可访问"));

        mockMvc.perform(get("/api/sheets/9"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.id").value(9));
        mockMvc.perform(get("/api/sheets/10"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.code").value("SHEET_NOT_FOUND"));
    }

    @Test
    void invalidSortAndPaginationAreRejectedBeforeServiceCall() throws Exception {
        mockMvc.perform(get("/api/sheets")
                        .param("sort", "id desc; drop table guitar_sheet")
                        .param("size", "51"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.code").value("VALIDATION_ERROR"));
        verifyNoInteractions(guitarSheetService);
    }
}
