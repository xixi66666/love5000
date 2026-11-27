package com.example.website.integration.health;

/**
 * 单个目标的健康探测结果。
 *
 * <p>不可变值对象，既用于聚合响应的 {@code services} 数组，也用于日志。健康的前提是
 * HTTP 2xx 且响应顶层布尔 {@code success=true}；{@code statusCode} 在连接失败或超时时为
 * {@code null}，{@code message} 仅在离线时有值，取自固定短码，不携带上游响应体。</p>
 */
public class ServiceHealthResult {

    private final String name;
    private final String url;
    private final boolean healthy;
    private final Integer statusCode;
    private final long durationMs;
    private final String message;

    private ServiceHealthResult(String name,
                                String url,
                                boolean healthy,
                                Integer statusCode,
                                long durationMs,
                                String message) {
        this.name = name;
        this.url = url;
        this.healthy = healthy;
        this.statusCode = statusCode;
        this.durationMs = durationMs;
        this.message = message;
    }

    /**
     * 构造健康结果。
     *
     * @param definition 目标定义，用于带出名称与地址
     * @param statusCode 实际 HTTP 状态码，调用方保证为 2xx
     * @param durationMs 本次探测耗时，单位毫秒
     * @return 健康结果，{@code message} 为 {@code null}
     */
    public static ServiceHealthResult healthy(ServiceHealthDefinition definition,
                                              int statusCode,
                                              long durationMs) {
        return new ServiceHealthResult(
                definition.getName(), definition.getUrl(), true, statusCode, durationMs, null);
    }

    /**
     * 构造离线结果。
     *
     * @param definition 目标定义，用于带出名称与地址
     * @param statusCode 已取得的 HTTP 状态码，连接类失败时为 {@code null}
     * @param durationMs 本次探测耗时，单位毫秒；任务未真正执行时可传 0
     * @param message    固定短提示，会进入响应与日志，不得携带响应体或凭据
     * @return 离线结果
     */
    public static ServiceHealthResult unhealthy(ServiceHealthDefinition definition,
                                                Integer statusCode,
                                                long durationMs,
                                                String message) {
        return new ServiceHealthResult(
                definition.getName(), definition.getUrl(), false, statusCode, durationMs, message);
    }

    public String getName() {
        return name;
    }

    public String getUrl() {
        return url;
    }

    public boolean isHealthy() {
        return healthy;
    }

    public Integer getStatusCode() {
        return statusCode;
    }

    public long getDurationMs() {
        return durationMs;
    }

    public String getMessage() {
        return message;
    }
}
