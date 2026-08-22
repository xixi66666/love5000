package com.example.website.integration.health;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;

@Service
public class ServiceHealthAggregator {

    private final ServiceHealthProperties properties;
    private final ServiceHealthChecker checker;
    private final Executor executor;

    public ServiceHealthAggregator(ServiceHealthProperties properties,
                                   ServiceHealthChecker checker,
                                   @Qualifier("serviceHealthExecutor") Executor executor) {
        this.properties = properties;
        this.checker = checker;
        this.executor = executor;
    }

    public ServiceHealthSummary checkAll() {
        List<CompletableFuture<ServiceHealthResult>> futures = new ArrayList<>();
        for (ServiceHealthDefinition definition : properties.getServices()) {
            try {
                futures.add(CompletableFuture
                        .supplyAsync(() -> checker.check(definition), executor)
                        .handle((result, error) -> error == null
                                ? result
                                : ServiceHealthResult.unhealthy(
                                        definition, null, 0, "Health check failed")));
            } catch (RuntimeException e) {
                futures.add(CompletableFuture.completedFuture(
                        ServiceHealthResult.unhealthy(
                                definition, null, 0, "Health check unavailable")));
            }
        }

        List<ServiceHealthResult> results = new ArrayList<>();
        boolean healthy = true;
        for (CompletableFuture<ServiceHealthResult> future : futures) {
            ServiceHealthResult result = future.join();
            results.add(result);
            healthy = healthy && result.isHealthy();
        }
        return new ServiceHealthSummary(true, healthy, results);
    }
}
