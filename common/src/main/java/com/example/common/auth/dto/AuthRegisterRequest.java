package com.example.common.auth.dto;

/**
 * 注册接口 {@code POST /api/auth/register} 的请求体。
 *
 * <p>字段原样接收，规范化（去空格、转小写）与用户名、密码策略校验集中在
 * {@code AuthServiceImpl}，本类只承担反序列化职责，不添加校验注解。</p>
 */
public class AuthRegisterRequest {

    private String username;

    private String password;

    /** 展示名，可为空；为空或仅含空白时由服务端回落到规范化后的用户名。 */
    private String displayName;

    public String getUsername() {
        return username;
    }

    public void setUsername(String username) {
        this.username = username;
    }

    public String getPassword() {
        return password;
    }

    public void setPassword(String password) {
        this.password = password;
    }

    public String getDisplayName() {
        return displayName;
    }

    public void setDisplayName(String displayName) {
        this.displayName = displayName;
    }
}
