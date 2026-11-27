package com.example.common.auth.service;

import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;

/**
 * 密码摘要服务，封装 BCrypt 的编码与比对。
 *
 * <p>无状态，可安全地在多线程间共享；使用 {@code BCryptPasswordEncoder} 的默认强度，
 * 同一明文每次编码都会带上不同的盐，所以只能通过 {@link #matches} 验证，
 * 不能比较摘要字符串本身。</p>
 *
 * <p>{@link #matches} 对格式非法的历史摘要会返回 {@code false} 而不是抛异常，
 * 调用方按「密码错误」处理即可。</p>
 */
public class AuthPasswordService {

    private final BCryptPasswordEncoder passwordEncoder = new BCryptPasswordEncoder();

    /**
     * 计算密码摘要。
     *
     * @param rawPassword 明文密码；长度上限由服务层限制为 72
     * @return 含随机盐、可直接入库的 BCrypt 摘要
     */
    public String hash(String rawPassword) {
        return passwordEncoder.encode(rawPassword);
    }

    /**
     * 校验明文与摘要是否匹配。
     *
     * @param rawPassword 待校验的明文密码
     * @param passwordHash 库中保存的 BCrypt 摘要
     * @return 摘要格式非法或不匹配时均为 {@code false}
     */
    public boolean matches(String rawPassword, String passwordHash) {
        return passwordEncoder.matches(rawPassword, passwordHash);
    }
}
