package com.example.guitar.favorite.service;

import com.example.guitar.favorite.dao.FavoriteDao;
import com.example.guitar.favorite.dto.FavoriteFolderRequest;
import com.example.guitar.favorite.model.FavoriteFolder;
import com.example.guitar.favorite.vo.FavoriteFolderResponse;
import com.example.guitar.sheet.vo.SheetSummaryResponse;
import com.example.guitar.web.GuitarApiException;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;

@Service
public class FavoriteServiceImpl implements FavoriteService {

    private static final String FOLDER_NAME_CONSTRAINT = "uk_guitar_favorite_folder_name";
    private static final String FAVORITE_CONSTRAINT = "uk_guitar_favorite";

    private final FavoriteDao favoriteDao;

    public FavoriteServiceImpl(FavoriteDao favoriteDao) {
        this.favoriteDao = favoriteDao;
    }

    @Override
    public List<FavoriteFolderResponse> listFolders(long userId) {
        validateUserId(userId);
        List<FavoriteFolderResponse> responses = new ArrayList<FavoriteFolderResponse>();
        for (FavoriteFolder folder : favoriteDao.findFoldersByUserId(userId)) {
            responses.add(toResponse(folder));
        }
        return responses;
    }

    @Override
    @Transactional
    public FavoriteFolderResponse createFolder(long userId, FavoriteFolderRequest request) {
        validateUserId(userId);
        FavoriteFolder folder = new FavoriteFolder();
        folder.setUserId(userId);
        folder.setName(normalizeName(request));
        folder.setSortOrder(request == null || request.getSortOrder() == null ? 0 : request.getSortOrder());
        try {
            requireAffected(favoriteDao.insertFolder(folder), "FOLDER_CREATE_FAILED", "收藏夹创建失败");
        } catch (DuplicateKeyException exception) {
            throw folderNameExists(exception);
        } catch (DataIntegrityViolationException exception) {
            if (containsConstraint(exception, FOLDER_NAME_CONSTRAINT)) {
                throw folderNameExists(exception);
            }
            throw exception;
        }
        FavoriteFolder created = favoriteDao.findOwnedFolder(folder.getId(), userId);
        if (created == null) {
            throw serverError("FOLDER_CREATE_FAILED", "收藏夹创建失败");
        }
        return toResponse(created);
    }

    @Override
    @Transactional
    public FavoriteFolderResponse updateFolder(long userId, long folderId, FavoriteFolderRequest request) {
        FavoriteFolder current = requireOwnedFolderForUpdate(userId, folderId);
        current.setName(normalizeName(request));
        if (request.getSortOrder() != null) {
            current.setSortOrder(request.getSortOrder());
        }
        try {
            requireAffected(favoriteDao.updateFolder(current), "FOLDER_UPDATE_FAILED", "收藏夹更新失败");
        } catch (DuplicateKeyException exception) {
            throw folderNameExists(exception);
        } catch (DataIntegrityViolationException exception) {
            if (containsConstraint(exception, FOLDER_NAME_CONSTRAINT)) {
                throw folderNameExists(exception);
            }
            throw exception;
        }
        FavoriteFolder updated = favoriteDao.findOwnedFolder(folderId, userId);
        if (updated == null) {
            throw folderNotFound();
        }
        return toResponse(updated);
    }

    @Override
    @Transactional
    public void deleteFolder(long userId, long folderId) {
        requireOwnedFolderForUpdate(userId, folderId);
        List<Long> sheetIds = favoriteDao.findSheetIdsByFolder(folderId, userId);
        int deletedRelations = favoriteDao.deleteFavoritesByFolder(folderId, userId);
        if (deletedRelations != sheetIds.size()) {
            throw serverError("FAVORITE_DELETE_FAILED", "收藏关系删除失败");
        }
        if (!sheetIds.isEmpty()) {
            int decremented = favoriteDao.decrementFavoriteCounts(sheetIds);
            if (decremented != sheetIds.size()) {
                throw serverError("FAVORITE_COUNT_UPDATE_FAILED", "收藏计数更新失败");
            }
        }
        requireAffected(favoriteDao.deleteFolder(folderId, userId), "FOLDER_DELETE_FAILED", "收藏夹删除失败");
    }

    @Override
    @Transactional
    public void addFavorite(long userId, long folderId, long sheetId) {
        requireOwnedFolderForUpdate(userId, folderId);
        validateSheetId(sheetId);
        if (favoriteDao.findPublishedSheetForUpdate(sheetId) == null) {
            throw sheetNotFound();
        }
        try {
            requireAffected(favoriteDao.insertFavorite(userId, folderId, sheetId),
                    "FAVORITE_CREATE_FAILED", "收藏添加失败");
        } catch (DuplicateKeyException exception) {
            throw favoriteExists(exception);
        } catch (DataIntegrityViolationException exception) {
            if (containsConstraint(exception, FAVORITE_CONSTRAINT)) {
                throw favoriteExists(exception);
            }
            throw exception;
        }
        if (favoriteDao.incrementFavoriteCount(sheetId) != 1) {
            throw sheetNotFound();
        }
    }

    @Override
    @Transactional
    public void removeFavorite(long userId, long folderId, long sheetId) {
        requireOwnedFolderForUpdate(userId, folderId);
        validateSheetId(sheetId);
        int deleted = favoriteDao.deleteFavorite(userId, folderId, sheetId);
        if (deleted == 0) {
            return;
        }
        if (deleted != 1) {
            throw serverError("FAVORITE_DELETE_FAILED", "收藏关系删除失败");
        }
        requireAffected(favoriteDao.decrementFavoriteCount(sheetId),
                "FAVORITE_COUNT_UPDATE_FAILED", "收藏计数更新失败");
    }

    @Override
    public List<SheetSummaryResponse> listSheets(long userId, long folderId) {
        validateUserId(userId);
        validateFolderId(folderId);
        if (favoriteDao.findOwnedFolder(folderId, userId) == null) {
            throw folderNotFound();
        }
        List<SheetSummaryResponse> sheets = favoriteDao.findPublishedSheetsByFolder(folderId, userId);
        return sheets == null ? Collections.<SheetSummaryResponse>emptyList() : sheets;
    }

    private FavoriteFolder requireOwnedFolderForUpdate(long userId, long folderId) {
        validateUserId(userId);
        validateFolderId(folderId);
        FavoriteFolder folder = favoriteDao.findOwnedFolderForUpdate(folderId, userId);
        if (folder == null) {
            throw folderNotFound();
        }
        return folder;
    }

    private String normalizeName(FavoriteFolderRequest request) {
        String name = request == null || request.getName() == null ? "" : request.getName().trim();
        if (name.isEmpty() || name.length() > 50) {
            throw new GuitarApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR",
                    "收藏夹名称长度必须为 1-50 个字符");
        }
        return name;
    }

    private void validateUserId(long userId) {
        if (userId < 1) {
            throw new GuitarApiException(HttpStatus.UNAUTHORIZED, "AUTH_REQUIRED", "请先登录");
        }
    }

    private void validateFolderId(long folderId) {
        if (folderId < 1) {
            throw folderNotFound();
        }
    }

    private void validateSheetId(long sheetId) {
        if (sheetId < 1) {
            throw sheetNotFound();
        }
    }

    private void requireAffected(int affected, String code, String message) {
        if (affected != 1) {
            throw serverError(code, message);
        }
    }

    private boolean containsConstraint(Throwable exception, String constraint) {
        Throwable current = exception;
        String expected = constraint.toLowerCase(Locale.ROOT);
        while (current != null) {
            String message = current.getMessage();
            if (message != null && message.toLowerCase(Locale.ROOT).contains(expected)) {
                return true;
            }
            current = current.getCause();
        }
        return false;
    }

    private FavoriteFolderResponse toResponse(FavoriteFolder folder) {
        return new FavoriteFolderResponse(folder.getId(), folder.getName(), folder.getSortOrder(),
                folder.getCreateTime(), folder.getUpdateTime());
    }

    private GuitarApiException folderNameExists(Throwable cause) {
        return apiException(HttpStatus.CONFLICT, "FOLDER_NAME_EXISTS", "收藏夹名称已存在", cause);
    }

    private GuitarApiException favoriteExists(Throwable cause) {
        return apiException(HttpStatus.CONFLICT, "FAVORITE_EXISTS", "该曲谱已在收藏夹中", cause);
    }

    private GuitarApiException folderNotFound() {
        return new GuitarApiException(HttpStatus.NOT_FOUND, "FOLDER_NOT_FOUND", "收藏夹不存在或不可访问");
    }

    private GuitarApiException sheetNotFound() {
        return new GuitarApiException(HttpStatus.NOT_FOUND, "SHEET_NOT_FOUND", "曲谱不存在或不可访问");
    }

    private GuitarApiException serverError(String code, String message) {
        return new GuitarApiException(HttpStatus.INTERNAL_SERVER_ERROR, code, message);
    }

    private GuitarApiException apiException(HttpStatus status, String code, String message, Throwable cause) {
        GuitarApiException exception = new GuitarApiException(status, code, message);
        exception.initCause(cause);
        return exception;
    }
}
