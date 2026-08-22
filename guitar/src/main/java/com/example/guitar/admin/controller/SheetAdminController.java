package com.example.guitar.admin.controller;

import com.example.guitar.admin.dto.AdminSheetSearchRequest;
import com.example.guitar.admin.dto.SheetOfflineRequest;
import com.example.guitar.admin.service.SheetAdminService;
import com.example.guitar.admin.vo.AdminSheetSummaryResponse;
import com.example.guitar.auth.model.GuitarUserPrincipal;
import com.example.guitar.auth.service.GuitarAuthService;
import com.example.guitar.web.ApiResponse;
import com.example.guitar.web.GuitarApiException;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.servlet.http.HttpServletRequest;

@RestController
@RequestMapping("/api/admin/sheets")
public class SheetAdminController {

    private final SheetAdminService sheetAdminService;
    private final GuitarAuthService guitarAuthService;

    public SheetAdminController(SheetAdminService sheetAdminService, GuitarAuthService guitarAuthService) {
        this.sheetAdminService = sheetAdminService;
        this.guitarAuthService = guitarAuthService;
    }

    @GetMapping
    public ApiResponse<SheetAdminService.AdminSheetSearchResult> list(
            @ModelAttribute AdminSheetSearchRequest searchRequest, HttpServletRequest request) {
        currentAdmin(request);
        return ApiResponse.success(sheetAdminService.list(searchRequest));
    }

    @PostMapping("/{id}/offline")
    public ApiResponse<AdminSheetSummaryResponse> offline(@PathVariable long id,
                                                          @RequestBody SheetOfflineRequest offlineRequest,
                                                          HttpServletRequest request) {
        GuitarUserPrincipal admin = currentAdmin(request);
        String reason = offlineRequest == null ? null : offlineRequest.getReason();
        return ApiResponse.success(sheetAdminService.offline(
                admin.getId(), id, reason, request.getRemoteAddr()));
    }

    @PostMapping("/{id}/restore")
    public ApiResponse<AdminSheetSummaryResponse> restore(@PathVariable long id, HttpServletRequest request) {
        GuitarUserPrincipal admin = currentAdmin(request);
        return ApiResponse.success(sheetAdminService.restore(admin.getId(), id, request.getRemoteAddr()));
    }

    private GuitarUserPrincipal currentAdmin(HttpServletRequest request) {
        GuitarUserPrincipal principal = guitarAuthService.currentSession(request).orElseThrow(() ->
                new GuitarApiException(HttpStatus.UNAUTHORIZED, "AUTH_REQUIRED", "请先登录"));
        if (!"ADMIN".equals(principal.getRole())) {
            throw new GuitarApiException(HttpStatus.FORBIDDEN, "ADMIN_REQUIRED", "需要管理员权限");
        }
        return principal;
    }
}
