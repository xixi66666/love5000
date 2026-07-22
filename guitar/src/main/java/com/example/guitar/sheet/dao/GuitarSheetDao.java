package com.example.guitar.sheet.dao;

import com.example.guitar.sheet.dto.SheetSearchRequest;
import com.example.guitar.sheet.model.GuitarSheet;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.time.LocalDate;
import java.util.List;

@Mapper
public interface GuitarSheetDao {

    long countPublicSheets(@Param("request") SheetSearchRequest request);

    List<GuitarSheet> findPublicSheets(@Param("request") SheetSearchRequest request);

    GuitarSheet findPublishedById(@Param("id") Long id);

    int incrementViewCount(@Param("id") Long id);

    int incrementDailyViewCount(@Param("statDate") LocalDate statDate);

    int insert(GuitarSheet sheet);

    GuitarSheet findActiveByIdForOwner(@Param("id") Long id, @Param("ownerId") Long ownerId);

    int existsActiveById(@Param("id") Long id);

    GuitarSheet findActiveByIdForOwnerForUpdate(@Param("id") Long id, @Param("ownerId") Long ownerId);

    int updateMetadata(@Param("sheet") GuitarSheet sheet);

    int updateStorageAndFileMode(@Param("sheet") GuitarSheet sheet);

    int markDeleted(@Param("id") Long id, @Param("ownerId") Long ownerId);

    int resetFavoriteCount(@Param("id") Long id);

    int deleteFavoritesBySheetId(@Param("sheetId") Long sheetId);
}
