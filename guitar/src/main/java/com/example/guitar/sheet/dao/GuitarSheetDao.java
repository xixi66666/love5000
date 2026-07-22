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
}
