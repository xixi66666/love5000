package com.example.website.auth;

import com.example.common.auth.model.AuthUser;
import com.example.common.auth.repository.AuthUserRepository;
import com.example.website.auth.dao.WebsiteAuthUserDao;
import org.springframework.stereotype.Repository;

import java.util.Optional;

/**
 * 把 {@code common} 模块的通用认证仓储接口 {@link AuthUserRepository} 适配到 {@code website}
 * 自己的用户表 {@code auth_user}。
 *
 * <p>{@code common} 只声明注册、登录与会话恢复所需的最小契约，本类负责把 DAO 的“查不到返回
 * {@code null}”转换成 {@link Optional}；SQL 全部由 {@link WebsiteAuthUserDao} 和
 * {@code mapper/auth/WebsiteAuthUserMapper.xml} 承担，这里不写任何语句，也不做密码校验。</p>
 *
 * <p>{@link #save} 依赖 Mapper 的 {@code useGeneratedKeys} 把自增主键回填到
 * {@link AuthUser#getId()} 后再返回。用户名唯一性由表上的唯一索引保证，重复注册时数据库报错，
 * Spring 会转换为 {@code DuplicateKeyException} 上抛，由认证控制器映射成可读的错误响应。</p>
 */
@Repository
public class WebsiteAuthUserRepository implements AuthUserRepository {

    private final WebsiteAuthUserDao websiteAuthUserDao;

    public WebsiteAuthUserRepository(WebsiteAuthUserDao websiteAuthUserDao) {
        this.websiteAuthUserDao = websiteAuthUserDao;
    }

    /**
     * 按登录名查用户，登录与重复注册检查都会用到。
     *
     * @param username 登录名，由认证控制器保证非空；不做大小写或空白归一化
     * @return 命中时返回包含密码哈希的用户；不存在时返回空 {@link Optional}，不抛异常
     */
    @Override
    public Optional<AuthUser> findByUsername(String username) {
        return Optional.ofNullable(websiteAuthUserDao.findByUsername(username));
    }

    /**
     * 按主键查用户，主要用于 Session 恢复登录态时重新加载用户资料。
     *
     * @param id {@code auth_user.id}，可为 {@code null}；为 {@code null} 时数据库不会命中
     * @return 命中时返回用户；不存在时返回空 {@link Optional}
     */
    @Override
    public Optional<AuthUser> findById(Long id) {
        return Optional.ofNullable(websiteAuthUserDao.findById(id));
    }

    /**
     * 插入新用户并返回数据库生成的主键。
     *
     * <p>密码以调用方传入的哈希形式直接落库，本类不做加密；角色缺省由认证服务决定。</p>
     *
     * @param username     登录名，必填，唯一索引冲突时写入失败
     * @param passwordHash 已经过 BCrypt 等算法处理的口令摘要，不是明文
     * @param displayName  展示名，可为 {@code null}
     * @param role         角色标识，例如普通用户或管理员
     * @return 新记录的自增主键，由 Mapper 回填到 {@link AuthUser}
     * @throws org.springframework.dao.DuplicateKeyException 用户名已存在时由 Spring 的异常转换抛出
     */
    @Override
    public Long save(String username, String passwordHash, String displayName, String role) {
        AuthUser authUser = new AuthUser();
        authUser.setUsername(username);
        authUser.setPasswordHash(passwordHash);
        authUser.setDisplayName(displayName);
        authUser.setRole(role);
        websiteAuthUserDao.insert(authUser);
        return authUser.getId();
    }
}
