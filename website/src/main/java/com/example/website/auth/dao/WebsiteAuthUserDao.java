package com.example.website.auth.dao;

import com.example.common.auth.model.AuthUser;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface WebsiteAuthUserDao {

    AuthUser findByUsername(@Param("username") String username);

    AuthUser findById(@Param("id") Long id);

    int insert(AuthUser authUser);
}
