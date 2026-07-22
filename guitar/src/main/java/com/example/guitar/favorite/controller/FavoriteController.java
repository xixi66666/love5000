package com.example.guitar.favorite.controller;

import com.example.guitar.auth.model.GuitarUserPrincipal;
import com.example.guitar.auth.service.GuitarAuthService;
import com.example.guitar.favorite.dto.FavoriteFolderRequest;
import com.example.guitar.favorite.service.FavoriteService;
import com.example.guitar.favorite.vo.FavoriteFolderResponse;
import com.example.guitar.sheet.vo.SheetSummaryResponse;
import com.example.guitar.web.ApiResponse;
import com.example.guitar.web.GuitarApiException;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.servlet.http.HttpServletRequest;
import java.util.List;

@RestController
@RequestMapping("/api/favorite-folders")
public class FavoriteController {

    private final FavoriteService favoriteService;
    private final GuitarAuthService guitarAuthService;

    public FavoriteController(FavoriteService favoriteService, GuitarAuthService guitarAuthService) {
        this.favoriteService = favoriteService;
        this.guitarAuthService = guitarAuthService;
    }

    @GetMapping
    public ApiResponse<List<FavoriteFolderResponse>> list(HttpServletRequest request) {
        return ApiResponse.success(favoriteService.listFolders(currentUserId(request)));
    }

    @PostMapping
    public ApiResponse<FavoriteFolderResponse> create(@RequestBody FavoriteFolderRequest folderRequest,
                                                       HttpServletRequest request) {
        return ApiResponse.success(favoriteService.createFolder(currentUserId(request), folderRequest));
    }

    @PutMapping("/{id}")
    public ApiResponse<FavoriteFolderResponse> update(@PathVariable Long id,
                                                       @RequestBody FavoriteFolderRequest folderRequest,
                                                       HttpServletRequest request) {
        return ApiResponse.success(favoriteService.updateFolder(currentUserId(request), requiredId(id), folderRequest));
    }

    @DeleteMapping("/{id}")
    public ApiResponse<Void> delete(@PathVariable Long id, HttpServletRequest request) {
        favoriteService.deleteFolder(currentUserId(request), requiredId(id));
        return ApiResponse.success(null);
    }

    @PostMapping("/{id}/sheets/{sheetId}")
    public ApiResponse<Void> addSheet(@PathVariable Long id, @PathVariable Long sheetId,
                                      HttpServletRequest request) {
        favoriteService.addFavorite(currentUserId(request), requiredId(id), requiredId(sheetId));
        return ApiResponse.success(null);
    }

    @DeleteMapping("/{id}/sheets/{sheetId}")
    public ApiResponse<Void> removeSheet(@PathVariable Long id, @PathVariable Long sheetId,
                                         HttpServletRequest request) {
        favoriteService.removeFavorite(currentUserId(request), requiredId(id), requiredId(sheetId));
        return ApiResponse.success(null);
    }

    @GetMapping("/{id}/sheets")
    public ApiResponse<List<SheetSummaryResponse>> listSheets(@PathVariable Long id,
                                                               HttpServletRequest request) {
        return ApiResponse.success(favoriteService.listSheets(currentUserId(request), requiredId(id)));
    }

    private long currentUserId(HttpServletRequest request) {
        GuitarUserPrincipal current = guitarAuthService.currentSession(request).orElseThrow(() ->
                new GuitarApiException(HttpStatus.UNAUTHORIZED, "AUTH_REQUIRED", "请先登录"));
        return current.getId();
    }

    private long requiredId(Long id) {
        if (id == null || id < 1) {
            throw new GuitarApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", "请求参数不正确");
        }
        return id;
    }
}
