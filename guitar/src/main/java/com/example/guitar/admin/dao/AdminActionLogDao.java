package com.example.guitar.admin.dao;

import com.example.guitar.admin.model.AdminActionLog;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface AdminActionLogDao {

    int insert(AdminActionLog actionLog);
}
