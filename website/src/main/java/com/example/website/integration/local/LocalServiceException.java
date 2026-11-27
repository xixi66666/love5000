package com.example.website.integration.local;

/**
 * 本机服务集成层的业务异常，携带要回给浏览器的 HTTP 状态码。
 *
 * <p>由 {@code LocalServicesController} 的异常处理器统一转成
 * {@code success=false} 加可读 {@code message}，因此消息必须是可直接展示的中文短句，
 * 不得包含凭据、绝对路径或上游响应体。常见状态码：400 参数非法或操作不受支持、
 * 403 非本机来源、404 未知服务、409 服务忙或进程不属于本项目、503 未就绪或执行失败。</p>
 */
public class LocalServiceException extends RuntimeException {
    /** 建议返回给浏览器的 HTTP 状态码。 */
    private final int status;

    /**
     * 构造异常。
     *
     * @param status  建议返回给浏览器的 HTTP 状态码
     * @param message 可直接展示给用户的中文说明
     */
    public LocalServiceException(int status, String message) {
        super(message);
        this.status = status;
    }

    public int getStatus() {
        return status;
    }
}
