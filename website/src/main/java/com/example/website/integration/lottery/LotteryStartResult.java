package com.example.website.integration.lottery;

/**
 * 开奖数据操作台一次点击启动的结果。
 *
 * <p>不可变值对象，只供 {@link LotteryController} 组装响应体，本身不保存进程状态；
 * 真实状态始终以健康探测为准。</p>
 */
public class LotteryStartResult {

    /** 本次调用新拉起子进程并确认健康；前端据此提示「已启动」。 */
    public static final String STATUS_STARTED = "started";
    /** 启动前探测到已有健康实例，直接复用、未新起进程。 */
    public static final String STATUS_ALREADY_RUNNING = "already-running";

    private final String status;
    private final String url;

    public LotteryStartResult(String status, String url) {
        this.status = status;
        this.url = url;
    }

    public String getStatus() {
        return status;
    }

    public String getUrl() {
        return url;
    }
}
