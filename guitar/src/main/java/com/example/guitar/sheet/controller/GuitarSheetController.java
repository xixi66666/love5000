package com.example.guitar.sheet.controller;

import com.example.guitar.sheet.dto.SheetSearchRequest;
import com.example.guitar.sheet.service.GuitarSheetService;
import com.example.guitar.sheet.vo.SheetDetailResponse;
import com.example.guitar.web.ApiResponse;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/sheets")
public class GuitarSheetController {

    private final GuitarSheetService guitarSheetService;

    public GuitarSheetController(GuitarSheetService guitarSheetService) {
        this.guitarSheetService = guitarSheetService;
    }

    @GetMapping
    public ApiResponse<GuitarSheetService.SheetSearchResult> search(@ModelAttribute SheetSearchRequest request) {
        request.normalizeAndValidate();
        return ApiResponse.success(guitarSheetService.searchPublicSheets(request));
    }

    @GetMapping("/{id}")
    public ApiResponse<SheetDetailResponse> detail(@PathVariable Long id) {
        return ApiResponse.success(guitarSheetService.getPublicSheetDetail(id));
    }
}
