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
 * 健康巡检的调度与快照缓存。
 *
 * <p>应用就绪后（{@link ApplicationReadyEvent}）先同步巡检一次，之后按
 * {@code website.service-health.check-interval-ms} 固定延迟重复，默认 1800000 毫秒
 * （30 分钟）。页面请求只读取最近结果，打开或刷新多个首页不会额外访问子服务。</p>
 *
 * <p>健康探测不持有快照锁：后台巡检运行时，已有的最近结果仍可立即返回。
 * 首次并发读取共用同一个探测，定时任务之间也不会重叠；探测失败保留旧快照。</p>
 *
 * <p>{@code website.service-health.scheduled-enabled=false} 时完全不注册定时任务，
 * 供单元测试关闭后台访问；此时首次读取仍会按需触发一次探测。</p>
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

    /**
     * 应用就绪后执行首轮巡检，并按固定延迟安排后续巡检。
     *
     * <p>首轮同步完成，保证启动后的第一个页面请求就能读到结果；探测期间不持有
     * {@code stateLock}，并发读取不会被阻塞。{@code scheduled-enabled=false} 时直接返回，
     * 单元测试据此避免访问真实服务。重复调用是幂等的：已有定时任务时不再新建。</p>
     */
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

    /**
     * 读取最近一次巡检结果，必要时同步补做一轮。
     *
     * <p>已有快照时立即返回，加锁前先读 volatile 字段以减少竞争；尚无快照时由首个调用者
     * 执行探测，其余并发调用等待同一个 {@link CompletableFuture}，不会重复探测。</p>
     *
     * @return 聚合结果，永不为 {@code null}
     */
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

    /**
     * 定时任务回调：执行一轮后台巡检。
     *
     * <p>若已有首读或上一轮巡检在跑，只等待它结束而不发起第二个探测，避免两轮叠加成倍
     * 访问子服务。上一轮失败不会中断调度，固定延迟会继续触发。</p>
     */
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

    /**
     * 执行一轮探测并原子替换快照。
     *
     * <p>聚合抛出运行时异常时保留上一轮结果（首次失败则给出空列表的离线汇总），
     * 并且无论成功与否都会完成 future，避免等待方永久挂起。快照替换与
     * {@code inFlight} 清空在同一把锁内完成，维持「有快照即无在途探测」的可见性。</p>
     *
     * @param probe 本轮探测对应的 future，由创建者持有并在结束后完成
     */
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

    /**
     * 等待探测完成，异常情况下退回已有快照。
     *
     * <p>被中断时恢复中断标记；{@code ExecutionException} 属防御分支，正常路径不会发生。
     * 极端情况下返回「未生成汇总」的空结果，保证 HTTP 响应结构稳定。</p>
     *
     * @param probe 在途探测
     * @return 探测结果或最近快照，永不为 {@code null}
     */
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

    /**
     * 容器关闭时停止后续巡检。
     *
     * <p>{@code cancel(false)} 不打断正在执行的探测，让在途 HTTP 请求自然结束；
     * 同时置位 {@code stopped}，防止关闭过程中 {@link #start()} 再注册新任务。</p>
     */
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
