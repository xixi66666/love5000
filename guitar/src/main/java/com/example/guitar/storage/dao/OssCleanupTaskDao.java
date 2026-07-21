package com.example.guitar.storage.dao;

import com.example.guitar.storage.model.OssCleanupTask;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface OssCleanupTaskDao {

    int insertPending(OssCleanupTask task);
}
