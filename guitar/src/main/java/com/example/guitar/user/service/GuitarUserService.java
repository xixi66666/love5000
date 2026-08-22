package com.example.guitar.user.service;

import com.example.guitar.auth.model.GuitarUserPrincipal;
import org.springframework.web.multipart.MultipartFile;

public interface GuitarUserService {

    GuitarUserPrincipal updateNickname(Long userId, String nickname);

    GuitarUserPrincipal updateAvatar(Long userId, MultipartFile avatar);
}
