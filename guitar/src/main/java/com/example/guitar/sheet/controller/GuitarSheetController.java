package com.example.guitar.sheet.controller;

import com.example.guitar.auth.model.GuitarUserPrincipal;
import com.example.guitar.auth.service.GuitarAuthService;
import com.example.guitar.sheet.dto.SheetSearchRequest;
import com.example.guitar.sheet.dto.SheetSaveRequest;
import com.example.guitar.sheet.service.GuitarSheetService;
import com.example.guitar.sheet.vo.SheetDetailResponse;
import com.example.guitar.web.ApiResponse;
import com.example.guitar.web.GuitarApiException;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import javax.servlet.http.HttpServletRequest;
import java.util.List;

@RestController
@RequestMapping("/api/sheets")
public class GuitarSheetController {

    private final GuitarSheetService guitarSheetService;
    private final GuitarAuthService guitarAuthService;

    public GuitarSheetController(GuitarSheetService guitarSheetService, GuitarAuthService guitarAuthService) {
        this.guitarSheetService = guitarSheetService;
        this.guitarAuthService = guitarAuthService;
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

    @PostMapping(consumes = "multipart/form-data")
    public ApiResponse<SheetDetailResponse> create(@RequestPart("metadata") SheetSaveRequest metadata,
                                                    @RequestPart("files") List<MultipartFile> files,
                                                    HttpServletRequest request) {
        GuitarUserPrincipal current = guitarAuthService.currentSession(request).orElseThrow(() ->
                new GuitarApiException(HttpStatus.UNAUTHORIZED, "AUTH_REQUIRED", "请先登录"));
        return ApiResponse.success(guitarSheetService.createSheet(current.getId(), current.getNickname(), metadata, files));
    }

    @PutMapping(value = "/{id}", consumes = "application/json")
    public ApiResponse<SheetDetailResponse> updateMetadata(@PathVariable Long id, @RequestBody SheetSaveRequest metadata,
                                                            HttpServletRequest request) {
        return ApiResponse.success(guitarSheetService.updateSheetMetadata(currentUser(request).getId(), id, metadata));
    }

    @PutMapping(value = "/{id}/files", consumes = "multipart/form-data")
    public ApiResponse<SheetDetailResponse> replaceFiles(@PathVariable Long id, @RequestPart("metadata") SheetSaveRequest metadata,
                                                          @RequestPart("files") List<MultipartFile> files, HttpServletRequest request) {
        return ApiResponse.success(guitarSheetService.replaceSheetFiles(currentUser(request).getId(), id, metadata, files));
    }

    @DeleteMapping("/{id}")
    public ApiResponse<Void> delete(@PathVariable Long id, HttpServletRequest request) {
        guitarSheetService.deleteSheet(currentUser(request).getId(), id);
        return ApiResponse.success(null);
    }

    private GuitarUserPrincipal currentUser(HttpServletRequest request) {
        return guitarAuthService.currentSession(request).orElseThrow(() ->
                new GuitarApiException(HttpStatus.UNAUTHORIZED, "AUTH_REQUIRED", "请先登录"));
    }
}
