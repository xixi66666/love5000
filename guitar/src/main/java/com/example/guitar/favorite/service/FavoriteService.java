package com.example.guitar.favorite.service;

import com.example.guitar.favorite.dto.FavoriteFolderRequest;
import com.example.guitar.favorite.vo.FavoriteFolderResponse;
import com.example.guitar.sheet.vo.SheetSummaryResponse;

import java.util.List;

public interface FavoriteService {

    List<FavoriteFolderResponse> listFolders(long userId);

    FavoriteFolderResponse createFolder(long userId, FavoriteFolderRequest request);

    FavoriteFolderResponse updateFolder(long userId, long folderId, FavoriteFolderRequest request);

    void deleteFolder(long userId, long folderId);

    void addFavorite(long userId, long folderId, long sheetId);

    void removeFavorite(long userId, long folderId, long sheetId);

    List<SheetSummaryResponse> listSheets(long userId, long folderId);
}
