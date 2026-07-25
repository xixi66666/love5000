package com.example.website.integration.health;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;

@Configuration
public class ServiceHealthConfiguration {

    @Bean(name = "serviceHealthExecutor")
    public ThreadPoolTaskExecutor serviceHealthExecutor(ServiceHealthProperties properties) {
        int poolSize = Math.max(1, properties.getServices().size());
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(poolSize);
        executor.setMaxPoolSize(poolSize);
        executor.setQueueCapacity(poolSize);
        executor.setThreadNamePrefix("service-health-");
        executor.setWaitForTasksToCompleteOnShutdown(true);
        executor.initialize();
        return executor;
    }
}
