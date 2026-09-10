package com.example.website.integration.health;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class ServiceHealthAggregatorTest {

    private ExecutorService executor;

    @AfterEach
    void shutdownExecutor() {
        if (executor != null) {
            executor.shutdownNow();
        }
    }

    @Test
    void preservesConfigurationOrderAndReportsPartialFailure() {
        ServiceHealthDefinition lovestory = definition("lovestory", 8081);
        ServiceHealthDefinition imagetemplate = definition("imagetemplate", 8082);
        ServiceHealthDefinition pythona = definition("python-a", 5174);
        ServiceHealthProperties properties = properties(lovestory, imagetemplate, pythona);
        ServiceHealthChecker checker = mock(ServiceHealthChecker.class);
        when(checker.check(lovestory)).thenReturn(ServiceHealthResult.healthy(lovestory, 200, 8));
        when(checker.check(imagetemplate)).thenReturn(ServiceHealthResult.healthy(imagetemplate, 200, 10));
        when(checker.check(pythona)).thenReturn(
                ServiceHealthResult.unhealthy(pythona, null, 3, "Connection failed"));
        executor = Executors.newFixedThreadPool(3);

        ServiceHealthSummary summary =
                new ServiceHealthAggregator(properties, checker, executor).checkAll();

        assertThat(summary.isSuccess()).isTrue();
        assertThat(summary.isHealthy()).isFalse();
        assertThat(summary.getServices())
                .extracting(ServiceHealthResult::getName)
                .containsExactly("lovestory", "imagetemplate", "python-a");
    }

    @Test
    void isolatesUnexpectedCheckerFailures() {
        ServiceHealthDefinition imagetemplate = definition("imagetemplate", 8082);
        ServiceHealthProperties properties = properties(imagetemplate);
        ServiceHealthChecker checker = mock(ServiceHealthChecker.class);
        when(checker.check(imagetemplate)).thenThrow(new IllegalStateException("private-token"));
        executor = Executors.newSingleThreadExecutor();

        ServiceHealthSummary summary =
                new ServiceHealthAggregator(properties, checker, executor).checkAll();

        assertThat(summary.isHealthy()).isFalse();
        assertThat(summary.getServices().get(0).getMessage()).isEqualTo("Health check failed");
        assertThat(summary.getServices().get(0).getMessage()).doesNotContain("private-token");
    }

    @Test
    void startsChecksConcurrently() throws Exception {
        ServiceHealthDefinition first = definition("first", 9001);
        ServiceHealthDefinition second = definition("second", 9002);
        ServiceHealthProperties properties = properties(first, second);
        CountDownLatch started = new CountDownLatch(2);
        CountDownLatch release = new CountDownLatch(1);
        ServiceHealthChecker checker = mock(ServiceHealthChecker.class);
        when(checker.check(any())).thenAnswer(invocation -> {
            ServiceHealthDefinition definition = invocation.getArgument(0);
            started.countDown();
            release.await(2, TimeUnit.SECONDS);
            return ServiceHealthResult.healthy(definition, 200, 1);
        });
        executor = Executors.newFixedThreadPool(2);

        java.util.concurrent.Future<ServiceHealthSummary> future =
                java.util.concurrent.CompletableFuture.supplyAsync(
                        () -> new ServiceHealthAggregator(properties, checker, executor).checkAll());

        assertThat(started.await(1, TimeUnit.SECONDS)).isTrue();
        release.countDown();
        assertThat(future.get(2, TimeUnit.SECONDS).isHealthy()).isTrue();
    }

    @Test
    void isolatesExecutorRejectionAsAServiceFailure() {
        ServiceHealthDefinition imagetemplate = definition("imagetemplate", 8082);
        ServiceHealthProperties properties = properties(imagetemplate);
        ServiceHealthChecker checker = mock(ServiceHealthChecker.class);

        ServiceHealthSummary summary = new ServiceHealthAggregator(
                properties,
                checker,
                command -> {
                    throw new java.util.concurrent.RejectedExecutionException("busy");
                }).checkAll();

        assertThat(summary.isSuccess()).isTrue();
        assertThat(summary.isHealthy()).isFalse();
        assertThat(summary.getServices().get(0).getMessage()).isEqualTo("Health check unavailable");
    }

    private ServiceHealthDefinition definition(String name, int port) {
        return new ServiceHealthDefinition(name, "http://127.0.0.1:" + port + "/api/health");
    }

    private ServiceHealthProperties properties(ServiceHealthDefinition... definitions) {
        ServiceHealthProperties properties = new ServiceHealthProperties();
        properties.setServices(Arrays.asList(definitions));
        return properties;
    }
}
