package com.example.guitar.admin.dao;

import com.example.guitar.admin.dto.AdminSheetSearchRequest;
import com.example.guitar.admin.vo.AdminSheetSummaryResponse;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface SheetAdminDao {

    long countSheets(@Param("request") AdminSheetSearchRequest request);

    List<AdminSheetSummaryResponse> findSheets(@Param("request") AdminSheetSearchRequest request);

    AdminSheetSummaryResponse findByIdForUpdate(@Param("id") long id);

    AdminSheetSummaryResponse findById(@Param("id") long id);

    int markOffline(@Param("id") long id, @Param("adminUserId") long adminUserId,
                    @Param("reason") String reason);

    int restore(@Param("id") long id);
}
