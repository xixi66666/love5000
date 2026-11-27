package com.example.website.integration.health;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;
import org.springframework.scheduling.concurrent.ThreadPoolTaskScheduler;

/**
 * 健康巡检的线程资源装配。
 *
 * <p>提供两个具名 Bean：{@code serviceHealthScheduler} 只负责定时触发，
 * {@code serviceHealthExecutor} 承担并发的单目标探测。拆开是为了避免长耗时的 HTTP 探测
 * 占满调度线程，让下一次巡检的时间点发生漂移。</p>
 */
@Configuration
public class ServiceHealthConfiguration {

    /**
     * 巡检调度器，单线程即可满足默认半小时一次的低频触发。
     *
     * <p>{@code removeOnCancelPolicy=true} 保证容器关闭时取消的定时任务不会继续留在
     * 队列中引用监听器。</p>
     *
     * @return 已配置但尚未初始化的调度器，由 Spring 负责初始化
     */
    @Bean(name = "serviceHealthScheduler")
    public ThreadPoolTaskScheduler serviceHealthScheduler() {
        ThreadPoolTaskScheduler scheduler = new ThreadPoolTaskScheduler();
        scheduler.setPoolSize(1);
        scheduler.setThreadNamePrefix("service-health-scheduler-");
        scheduler.setRemoveOnCancelPolicy(true);
        return scheduler;
    }

    /**
     * 单目标探测线程池，线程数按目标数量取，保证一轮巡检真正并行。
     *
     * <p>核心线程数、最大线程数与队列容量一致（至少 1），避免任务在队列中排队拖长整轮
     * 耗时；关闭时等待在途任务结束，防止容器停止时留下半截 HTTP 请求。</p>
     *
     * @param properties 提供目标清单，用来确定池大小
     * @return 已配置但尚未初始化的执行器，由 Spring 负责初始化
     */
    @Bean(name = "serviceHealthExecutor")
    public ThreadPoolTaskExecutor serviceHealthExecutor(ServiceHealthProperties properties) {
        int poolSize = Math.max(1, properties.getServices().size());
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(poolSize);
        executor.setMaxPoolSize(poolSize);
        executor.setQueueCapacity(poolSize);
        executor.setThreadNamePrefix("service-health-");
        executor.setWaitForTasksToCompleteOnShutdown(true);
        return executor;
    }
}
