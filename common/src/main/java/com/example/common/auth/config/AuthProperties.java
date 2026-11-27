package com.example.common.auth.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * {@code love530.auth} 前缀下的认证配置绑定对象。
 *
 * <p>由 {@code AuthAutoConfiguration} 通过 {@code @EnableConfigurationProperties} 注册，
 * 业务模块无需再自行声明。三项配置分别控制能力开关、Session 属性名和密码长度下限；
 * 长度上限固定为 72（BCrypt 的有效输入上限），刻意不开放配置，避免摘要被静默截断。</p>
 */
@ConfigurationProperties(prefix = "love530.auth")
public class AuthProperties {

    /** 认证能力总开关，默认开启；置为 {@code false} 时整个 AuthAutoConfiguration 不生效。 */
    private boolean enabled = true;

    /**
     * 登录主体在 {@code HttpSession} 中的属性名，读写两侧共用。
     * 修改后已有会话中的登录态会立即失效，需要用户重新登录。
     */
    private String sessionAttribute = "LOVE530_AUTH_USER";

    /** 注册密码的最小长度，默认 8；超过 72 的部分不会参与 BCrypt 摘要计算。 */
    private int minPasswordLength = 8;

    public boolean isEnabled() {
        return enabled;
    }

    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
    }

    public String getSessionAttribute() {
        return sessionAttribute;
    }

    public void setSessionAttribute(String sessionAttribute) {
        this.sessionAttribute = sessionAttribute;
    }

    public int getMinPasswordLength() {
        return minPasswordLength;
    }

    public void setMinPasswordLength(int minPasswordLength) {
        this.minPasswordLength = minPasswordLength;
    }
}
