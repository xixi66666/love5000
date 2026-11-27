package com.example.website.integration.personalagent;

/**
 * 个人资料库启动失败。
 *
 * <p>{@code message} 是直接展示给用户的中文原因，涵盖「端口被占用或已有实例未就绪」、
 * 「尚未构建 jar」、「Java 无法执行」和「等待超时」四类；
 * {@link PersonalAgentController} 会把它放进 HTTP 503 的 {@code message}。
 * 继承 {@link RuntimeException} 以免污染启动方法的签名。</p>
 */
public class PersonalAgentStartException extends RuntimeException {

    public PersonalAgentStartException(String message) {
        super(message);
    }
}
