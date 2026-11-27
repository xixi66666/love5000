package com.example.website.integration.lottery;

/**
 * 开奖数据操作台启动失败。
 *
 * <p>{@code message} 是面向用户的中文原因（缺少 {@code server.py}、{@code python}
 * 不可执行、等待超时等），{@link LotteryController} 会原样放进 HTTP 503 响应体的
 * {@code message}。继承 {@link RuntimeException} 以免污染启动方法的签名；该异常表示
 * 本次启动确实失败，不属于可自动重试的瞬时故障。</p>
 */
public class LotteryStartException extends RuntimeException {

    private static final long serialVersionUID = 1L;

    public LotteryStartException(String message) {
        super(message);
    }
}
