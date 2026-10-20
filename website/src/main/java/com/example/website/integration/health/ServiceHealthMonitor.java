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
import java.util.concurrent.ScheduledFuture;

/** 项目启动巡检一次，之后固定间隔巡检；页面请求只读取最近结果。 */
@Service
public class ServiceHealthMonitor {

    private static final Logger log = LoggerFactory.getLogger(ServiceHealthMonitor.class);

    private final ServiceHealthAggregator aggregator;
    private final ServiceHealthProperties properties;
    private final TaskScheduler scheduler;
    private ServiceHealthSummary latest;
    private ScheduledFuture<?> scheduledCheck;

    public ServiceHealthMonitor(ServiceHealthAggregator aggregator,
                                ServiceHealthProperties properties,
                                @Qualifier("serviceHealthScheduler") TaskScheduler scheduler) {
        this.aggregator = aggregator;
        this.properties = properties;
        this.scheduler = scheduler;
    }

    @EventListener(ApplicationReadyEvent.class)
    public synchronized void start() {
        if (!properties.isScheduledEnabled() || scheduledCheck != null) {
            return;
        }
        snapshot();
        long interval = properties.getCheckIntervalMs();
        scheduledCheck = scheduler.scheduleWithFixedDelay(
                this::refresh, new Date(System.currentTimeMillis() + interval), interval);
        log.info("[健康检查][项目=website] 启动巡检完成，后续巡检间隔={}分钟", interval / 60000);
    }

    public synchronized ServiceHealthSummary snapshot() {
        // 首次请求与启动事件共享同一份结果，多个标签页不会重复触发巡检。
        if (latest == null) {
            refresh();
        }
        return latest;
    }

    private synchronized void refresh() {
        try {
            latest = aggregator.checkAll();
        } catch (RuntimeException exception) {
            log.warn("[健康检查][项目=website] 汇总检查失败，保留上次结果");
            if (latest == null) {
                latest = new ServiceHealthSummary(false, false, Collections.emptyList());
            }
        }
    }

    @PreDestroy
    public synchronized void stop() {
        if (scheduledCheck != null) {
            scheduledCheck.cancel(false);
        }
    }
}
