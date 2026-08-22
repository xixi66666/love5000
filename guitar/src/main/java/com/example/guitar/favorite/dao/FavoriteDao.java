package com.example.guitar.favorite.dao;

import com.example.guitar.favorite.model.FavoriteFolder;
import com.example.guitar.sheet.vo.SheetSummaryResponse;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface FavoriteDao {

    List<FavoriteFolder> findFoldersByUserId(@Param("userId") Long userId);

    FavoriteFolder findOwnedFolder(@Param("folderId") Long folderId, @Param("userId") Long userId);

    FavoriteFolder findOwnedFolderForUpdate(@Param("folderId") Long folderId, @Param("userId") Long userId);

    int insertFolder(FavoriteFolder folder);

    int updateFolder(FavoriteFolder folder);

    int deleteFolder(@Param("folderId") Long folderId, @Param("userId") Long userId);

    Long findPublishedSheetForUpdate(@Param("sheetId") Long sheetId);

    int insertFavorite(@Param("userId") Long userId, @Param("folderId") Long folderId,
                       @Param("sheetId") Long sheetId);

    int deleteFavorite(@Param("userId") Long userId, @Param("folderId") Long folderId,
                       @Param("sheetId") Long sheetId);

    int incrementFavoriteCount(@Param("sheetId") Long sheetId);

    int decrementFavoriteCount(@Param("sheetId") Long sheetId);

    List<Long> findSheetIdsByFolder(@Param("folderId") Long folderId, @Param("userId") Long userId);

    int deleteFavoritesByFolder(@Param("folderId") Long folderId, @Param("userId") Long userId);

    int decrementFavoriteCounts(@Param("sheetIds") List<Long> sheetIds);

    List<SheetSummaryResponse> findPublishedSheetsByFolder(@Param("folderId") Long folderId,
                                                            @Param("userId") Long userId);
}
