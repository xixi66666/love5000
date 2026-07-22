package com.example.guitar.sheet.dao;

import com.example.guitar.sheet.model.GuitarSheetFile;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface GuitarSheetFileDao {

    List<GuitarSheetFile> findBySheetId(@Param("sheetId") Long sheetId);

    int insertBatch(@Param("files") List<GuitarSheetFile> files);

    int deleteBySheetId(@Param("sheetId") Long sheetId);
}
