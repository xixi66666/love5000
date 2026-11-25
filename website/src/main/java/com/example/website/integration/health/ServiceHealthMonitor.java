package com.example.website.integration.health;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.scheduling.TaskScheduler;
import org.springframework.stereotype.Service;

import javax.annotation.PreDestroy;
import java.util.Collections;
import java.util.Date;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ScheduledFuture;

/**
 * 项目启动巡检一次，之后固定间隔巡检；页面请求只读取最近结果。
 *
 * <p>健康探测不持有快照锁：后台巡检运行时，已有的最近结果仍可立即返回。
 * 首次并发读取共用同一个探测，定时任务之间也不会重叠；探测失败保留旧快照。</p>
 */
@Service
public class ServiceHealthMonitor {

    private static final Logger log = LoggerFactory.getLogger(ServiceHealthMonitor.class);

    private final ServiceHealthAggregator aggregator;
    private final ServiceHealthProperties properties;
    private final TaskScheduler scheduler;
    private final Object stateLock = new Object();

    /*
     * 状态约定：
     * - latest == null 且 inFlight == null：尚未巡检，首读触发探测；
     * - latest != null 且 inFlight == null：巡检完成，读路径直接返回；
     * - latest != null 且 inFlight != null：正在巡检，读路径立即返回上次结果。
     * 响应结构不增加字段，仍以 HTTP 200 + success / healthy / services 表达聚合结果。
     */

    /**
     * 最近一次完成巡检的结果。只在探测结束后整体替换，读路径不需要加锁。
     */
    private volatile ServiceHealthSummary latest;

    /**
     * 正在执行的探测。首读和定时任务通过它合并为一次探测，避免并发重叠。
     */
    private CompletableFuture<ServiceHealthSummary> inFlight;
    private ScheduledFuture<?> scheduledCheck;
    private boolean stopped;

    public ServiceHealthMonitor(ServiceHealthAggregator aggregator,
                                ServiceHealthProperties properties,
                                @Qualifier("serviceHealthScheduler") TaskScheduler scheduler) {
        this.aggregator = aggregator;
        this.properties = properties;
        this.scheduler = scheduler;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void start() {
        if (!properties.isScheduledEnabled()) {
            return;
        }
        synchronized (stateLock) {
            if (stopped || scheduledCheck != null) {
                return;
            }
        }

        // 启动阶段的首次巡检同步完成，保证启动后第一个请求已有结果。
        // 探测过程中不持有 stateLock，已有快照的读取不会被阻塞。
        snapshot();

        long interval = properties.getCheckIntervalMs();
        synchronized (stateLock) {
            if (stopped || scheduledCheck != null) {
                return;
            }
            scheduledCheck = scheduler.scheduleWithFixedDelay(
                    this::refresh, new Date(System.currentTimeMillis() + interval), interval);
        }
        log.info("[健康检查][项目=website] 启动巡检完成，后续巡检间隔={}分钟", interval / 60000);
    }

    public ServiceHealthSummary snapshot() {
        ServiceHealthSummary current = latest;
        if (current != null) {
            return current;
        }

        CompletableFuture<ServiceHealthSummary> probe;
        boolean owner = false;
        synchronized (stateLock) {
            current = latest;
            if (current != null) {
                return current;
            }
            probe = inFlight;
            if (probe == null) {
                probe = new CompletableFuture<>();
                inFlight = probe;
                owner = true;
            }
        }
        if (owner) {
            runProbe(probe);
        }
        return await(probe);
    }

    private void refresh() {
        CompletableFuture<ServiceHealthSummary> probe;
        boolean owner = false;
        synchronized (stateLock) {
            probe = inFlight;
            if (probe == null) {
                probe = new CompletableFuture<>();
                inFlight = probe;
                owner = true;
            }
        }
        if (owner) {
            runProbe(probe);
        } else {
            // 已有首读或上一轮巡检在跑，等待它完成，不再发起第二个探测。
            await(probe);
        }
    }

    private void runProbe(CompletableFuture<ServiceHealthSummary> probe) {
        ServiceHealthSummary next;
        try {
            next = aggregator.checkAll();
            if (next == null) {
                throw new IllegalStateException("health aggregate returned null");
            }
        } catch (RuntimeException exception) {
            log.warn("[健康检查][项目=website] 汇总检查失败，保留上次结果");
            next = latest;
            if (next == null) {
                next = new ServiceHealthSummary(false, false, Collections.emptyList());
            }
        }

        synchronized (stateLock) {
            latest = next;
            inFlight = null;
        }
        probe.complete(next);
    }

    private ServiceHealthSummary await(CompletableFuture<ServiceHealthSummary> probe) {
        try {
            return probe.get();
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
        } catch (ExecutionException exception) {
            // runProbe 正常路径总会正常完成 future；这里防御性返回已有结果。
        }
        ServiceHealthSummary current = latest;
        return current == null
                ? new ServiceHealthSummary(false, false, Collections.emptyList())
                : current;
    }

    @PreDestroy
    public void stop() {
        synchronized (stateLock) {
            stopped = true;
            if (scheduledCheck != null) {
                scheduledCheck.cancel(false);
            }
        }
    }
}
