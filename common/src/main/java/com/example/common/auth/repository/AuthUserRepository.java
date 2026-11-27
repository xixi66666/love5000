package com.example.common.auth.repository;

import com.example.common.auth.model.AuthUser;

import java.util.Optional;

/**
 * 认证用户仓储接口，是 {@code common} 认证能力与业务持久化层之间的唯一契约。
 *
 * <p>{@code common} 不提供实现，也不写任何 SQL：各业务模块用 MyBatis DAO + XML Mapper
 * 实现本接口并注册为 Bean。{@code AuthAutoConfiguration} 只有在容器中存在本接口的 Bean
 * 时才装配 {@code AuthService} 及其下游组件，缺失时认证能力整体降级，
 * 因此依赖认证的模块必须自己补上这个实现。</p>
 */
public interface AuthUserRepository {

    /**
     * 按登录名查询用户。
     *
     * <p>入参已经过服务层去空格并转小写，实现方按等值匹配即可；
     * 是否大小写敏感取决于表的排序规则，需与实现保持一致。</p>
     *
     * @param username 规范化后的登录名
     * @return 命中时返回用户记录，否则返回空 Optional
     */
    Optional<AuthUser> findByUsername(String username);

    /**
     * 按主键查询用户，供注册成功后回读完整记录。
     *
     * @param id 主键
     * @return 命中时返回用户记录；返回空 Optional 会让注册接口以 500 失败
     */
    Optional<AuthUser> findById(Long id);

    /**
     * 新增用户并返回主键。
     *
     * <p>{@code passwordHash} 已由服务层完成 BCrypt 编码，实现方不得再次编码，
     * 否则登录比对必然失败。</p>
     *
     * @param username 规范化后的登录名，调用前已确认未被占用
     * @param passwordHash BCrypt 摘要，不是明文密码
     * @param displayName 展示名，空值已由服务层回落到用户名
     * @param role 角色标识，注册流程固定传入 {@code USER}
     * @return 新记录的主键
     */
    Long save(String username, String passwordHash, String displayName, String role);
}
