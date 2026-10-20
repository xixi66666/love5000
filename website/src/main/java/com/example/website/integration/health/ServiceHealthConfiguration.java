package com.example.website.integration.health;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;
import org.springframework.scheduling.concurrent.ThreadPoolTaskScheduler;

@Configuration
public class ServiceHealthConfiguration {

    @Bean(name = "serviceHealthScheduler")
    public ThreadPoolTaskScheduler serviceHealthScheduler() {
        ThreadPoolTaskScheduler scheduler = new ThreadPoolTaskScheduler();
        scheduler.setPoolSize(1);
        scheduler.setThreadNamePrefix("service-health-scheduler-");
        scheduler.setRemoveOnCancelPolicy(true);
        return scheduler;
    }

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
