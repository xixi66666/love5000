package com.ycxandwuqian.love.dao;

import com.ycxandwuqian.love.model.GuitarVideoRecord;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface GuitarVideoDao {

    int insert(GuitarVideoRecord guitarVideoRecord);

    List<GuitarVideoRecord> findVisible();

    GuitarVideoRecord findById(@Param("id") Long id);

    int updateCoverUrl(@Param("id") Long id, @Param("coverUrl") String coverUrl);

    int hideById(@Param("id") Long id);
}
