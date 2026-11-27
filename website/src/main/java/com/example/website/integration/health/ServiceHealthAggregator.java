package com.example.website.integration.health;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;

/**
 * 并行健康巡检聚合器。
 *
 * <p>位于 integration/health 的编排层：按
 * {@code website.service-health.services} 的配置顺序，把每个目标交给
 * {@code serviceHealthExecutor} 线程池各起一个探测，由 {@link ServiceHealthChecker}
 * 完成单目标的 HTTP 判定。默认 11 个目标，聚合耗时约等于最慢的一个目标，
 * 而不是各目标超时之和。</p>
 *
 * <p>故障隔离：单目标探测抛出的异常被转换成该目标的离线结果，不会让整轮巡检失败；
 * 只有线程池拒绝任务时才降级为「Health check unavailable」。返回列表保持配置顺序，
 * 前端可以按固定顺序渲染入口状态。</p>
 *
 * <p>响应语义：{@code success} 恒为 {@code true}，表示巡检已生成汇总（全部离线也是
 * 汇总）；{@code healthy} 才表示所有目标都在线。</p>
 */
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

    /**
     * 对所有配置目标并发巡检一轮。
     *
     * <p>先为每个目标提交异步探测并挂上异常兜底，再按提交顺序 {@code join}，
     * 因此总耗时由最慢的目标决定，结果顺序稳定。</p>
     *
     * @return 聚合结果，{@code services} 按配置顺序保存单目标明细；任一目标离线时
     *         {@link ServiceHealthSummary#isHealthy()} 为 {@code false}
     */
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
