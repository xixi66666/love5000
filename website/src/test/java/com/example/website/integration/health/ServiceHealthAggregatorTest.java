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

/**
 * 并行巡检聚合器 {@link ServiceHealthAggregator} 的单元测试。
 *
 * <p>固定住四条对外契约：结果顺序与 {@code website.service-health.services} 的配置顺序一致
 * （首页按项目名匹配卡片，乱序会错配状态点）；部分目标离线时仍返回 {@code success=true}
 * （表示汇总已生成），{@code healthy=false} 才表示并非全部在线；单个
 * {@link ServiceHealthChecker} 抛异常只影响自己那一项，文案固定为 {@code Health check failed}
 * 且不回显异常内容（异常信息里可能带凭据）；线程池拒绝任务时降级为
 * {@code Health check unavailable}，不让整轮聚合失败。</p>
 *
 * <p>隔离：checker 全部用 Mockito mock，聚合器只在测试线程和自建线程池里跑，
 * 不发任何 HTTP 请求、不连 MySQL；executor 由各用例创建并在
 * {@link #shutdownExecutor()} 回收，避免残留线程拖住 Surefire。</p>
 */
class ServiceHealthAggregatorTest {

    private ExecutorService executor;

    // 线程池必须显式回收：聚合器不负责关闭外部传入的 executor。
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
            // 两个探测都进入后才放行，证明聚合器是并行下发而不是串行排队。
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

    /** 构造指向本机给定端口的检测目标（{@code http://127.0.0.1:端口/api/health}）。 */
    private ServiceHealthDefinition definition(String name, int port) {
        return new ServiceHealthDefinition(name, "http://127.0.0.1:" + port + "/api/health");
    }

    /** 用固定顺序的清单构造配置；入参顺序即配置顺序，也是聚合结果应保持的顺序。 */
    private ServiceHealthProperties properties(ServiceHealthDefinition... definitions) {
        ServiceHealthProperties properties = new ServiceHealthProperties();
        properties.setServices(Arrays.asList(definitions));
        return properties;
    }
}
