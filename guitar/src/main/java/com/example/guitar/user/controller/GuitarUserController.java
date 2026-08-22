package com.example.guitar.user.controller;

import com.example.guitar.auth.model.GuitarUserPrincipal;
import com.example.guitar.auth.service.GuitarAuthService;
import com.example.guitar.user.dto.UpdateProfileRequest;
import com.example.guitar.user.service.GuitarUserService;
import com.example.guitar.web.ApiResponse;
import com.example.guitar.web.GuitarApiException;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpSession;

@RestController
@RequestMapping("/api/users/me")
public class GuitarUserController {

    private final GuitarUserService guitarUserService;
    private final GuitarAuthService guitarAuthService;

    public GuitarUserController(GuitarUserService guitarUserService, GuitarAuthService guitarAuthService) {
        this.guitarUserService = guitarUserService;
        this.guitarAuthService = guitarAuthService;
    }

    @PutMapping
    public ApiResponse<GuitarUserPrincipal> updateProfile(@RequestBody UpdateProfileRequest request,
                                                           HttpServletRequest httpRequest) {
        GuitarUserPrincipal current = currentPrincipal(httpRequest);
        GuitarUserPrincipal updated = guitarUserService.updateNickname(current.getId(),
                request == null ? null : request.getNickname());
        refreshSessionPrincipal(httpRequest, updated);
        return ApiResponse.success(updated);
    }

    @org.springframework.web.bind.annotation.PostMapping("/avatar")
    public ApiResponse<GuitarUserPrincipal> updateAvatar(@RequestParam("avatar") MultipartFile avatar,
                                                          HttpServletRequest httpRequest) {
        GuitarUserPrincipal current = currentPrincipal(httpRequest);
        GuitarUserPrincipal updated = guitarUserService.updateAvatar(current.getId(), avatar);
        refreshSessionPrincipal(httpRequest, updated);
        return ApiResponse.success(updated);
    }

    private GuitarUserPrincipal currentPrincipal(HttpServletRequest request) {
        return guitarAuthService.currentSession(request).orElseThrow(() ->
                new GuitarApiException(HttpStatus.UNAUTHORIZED, "AUTH_REQUIRED", "请先登录"));
    }

    private void refreshSessionPrincipal(HttpServletRequest request, GuitarUserPrincipal principal) {
        HttpSession session = request.getSession(false);
        if (session == null) {
            throw new GuitarApiException(HttpStatus.UNAUTHORIZED, "AUTH_REQUIRED", "请先登录");
        }
        session.setAttribute(GuitarAuthService.SESSION_ATTRIBUTE, principal);
    }
}
