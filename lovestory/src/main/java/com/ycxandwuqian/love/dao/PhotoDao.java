package com.ycxandwuqian.love.dao;

import com.ycxandwuqian.love.model.PhotoRecord;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface PhotoDao {

    int insert(PhotoRecord photoRecord);

    List<PhotoRecord> findAll();

    PhotoRecord findById(@Param("id") Long id);

    int deleteById(@Param("id") Long id);
}
