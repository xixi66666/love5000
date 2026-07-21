package com.example.guitar.user.dao;

import com.example.guitar.user.model.GuitarUser;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.time.LocalDateTime;

@Mapper
public interface GuitarUserDao {

    GuitarUser findByPhone(@Param("phone") String phone);

    GuitarUser findById(@Param("id") Long id);

    int insert(GuitarUser user);

    int updateLastLoginAt(@Param("id") Long id, @Param("lastLoginAt") LocalDateTime lastLoginAt);

    int updateProfile(@Param("id") Long id,
                      @Param("nickname") String nickname,
                      @Param("avatarObjectKey") String avatarObjectKey);
}
