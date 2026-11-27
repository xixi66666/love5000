package com.example.website.auth.dao;

import com.example.common.auth.model.AuthUser;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

/**
 * {@code auth_user} 表的 MyBatis DAO。
 *
 * <p>SQL 全部写在 {@code mapper/auth/WebsiteAuthUserMapper.xml}，本接口不拼语句；查询结果由该文件的
 * {@code AuthUserResultMap} 映射到 {@code common} 的 {@link AuthUser}，因此下划线列名
 * （{@code display_name}、{@code password_hash}）到驼峰属性的转换不依赖全局开关。</p>
 *
 * <p>查询方法未命中时返回 {@code null}，由 {@link com.example.website.auth.WebsiteAuthUserRepository}
 * 统一转换为 {@code Optional}；插入使用自增主键回填。</p>
 */
@Mapper
public interface WebsiteAuthUserDao {

    /**
     * 按登录名精确匹配用户。
     *
     * @param username 登录名，区分大小写与首尾空白，由调用方负责归一化
     * @return 命中时返回用户，未命中返回 {@code null}
     */
    AuthUser findByUsername(@Param("username") String username);

    /**
     * 按主键查用户。
     *
     * @param id {@code auth_user.id}
     * @return 命中时返回用户，未命中返回 {@code null}
     */
    AuthUser findById(@Param("id") Long id);

    /**
     * 插入用户，只写入用户名、密码哈希、展示名和角色，其余列取表默认值。
     *
     * @param authUser 待插入用户，成功后其 {@code id} 被回填
     * @return 受影响行数，正常为 1
     */
    int insert(AuthUser authUser);
}
