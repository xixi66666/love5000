package com.example.website.integration.scrapling;

/**
 * Scrapling 抓取工坊启动失败。
 *
 * <p>{@code message} 是面向用户的中文原因（缺少后端目录、前端未构建、解释器不可执行、
 * 等待超时等），{@link ScraplingUiController} 会原样放进 HTTP 503 响应体的
 * {@code message}。继承 {@link RuntimeException} 以免污染启动方法的签名。</p>
 */
public class ScraplingUiStartException extends RuntimeException {

    public ScraplingUiStartException(String message) {
        super(message);
    }
}
