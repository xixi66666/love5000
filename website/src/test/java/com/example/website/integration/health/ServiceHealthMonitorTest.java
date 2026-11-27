package com.example.website.integration.health;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.scheduling.TaskScheduler;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Date;
import java.util.List;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.Callable;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doReturn;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

/**
 * 后台巡检调度器 {@link ServiceHealthMonitor} 的调度与并发测试。
 *
 * <p>固定住的行为：{@code start()} 只巡检一次，并注册固定延迟任务（间隔 1800000ms，即 30 分钟，
 * 首次执行时间不早于「现在 + 间隔」）；重复调用 {@code start()} 是幂等的；浏览器先读、
 * 启动事件后到，两者共用同一次探测；定时任务抛异常时保留上一份快照，不让接口变成空结果；
 * {@code scheduled-enabled=false} 时完全不接触调度器；刷新探测进行中 {@code snapshot()}
 * 仍立即返回旧快照而不阻塞；并发首读共享同一个慢探测；两个定时回调同时触发也只跑一个探测。</p>
 *
 * <p>隔离：{@link TaskScheduler} 与 {@link ScheduledFuture} 都是 mock，测试把注册进去的回调
 * 捕获出来自己 {@code run()}，用「手动触发一次」代替真的等 30 分钟；聚合器换成
 * {@link ControlledAggregator}，每次探测由 {@link Probe} 的闩锁控制进入与放行，
 * 全程不发 HTTP 请求、不连 MySQL。线程池在 {@link #shutdownExecutor()} 中回收。</p>
 */
class ServiceHealthMonitorTest {

    /** 单个用例的等待上限；并发用例宁可失败也不要在 CI 上挂死。 */
    private static final long TIMEOUT_SECONDS = 5;

    private final TaskScheduler scheduler = mock(TaskScheduler.class);
    private final ScheduledFuture<?> future = mock(ScheduledFuture.class);
    private final ServiceHealthProperties properties = new ServiceHealthProperties();
    /** 三个快照依次是「在线 → 部分离线 → 在线」，用来验证快照被整体替换而不是就地修改。 */
    private final ServiceHealthSummary first =
            new ServiceHealthSummary(true, true, Collections.emptyList());
    private final ServiceHealthSummary second =
            new ServiceHealthSummary(true, false, Collections.emptyList());
    private final ServiceHealthSummary third =
            new ServiceHealthSummary(true, true, Collections.emptyList());

    private ExecutorService executor;

    @AfterEach
    void shutdownExecutor() {
        // 用例里自己起的线程池由用例负责关，否则非守护线程会拖住测试进程退出。
        if (executor != null) {
            executor.shutdownNow();
        }
    }

    @Test
    void checksOnceAtStartupAndSchedulesNextCheckThirtyMinutesLater() throws Exception {
        ControlledAggregator aggregator = new ControlledAggregator();
        aggregator.enqueueImmediate(first);
        ServiceHealthMonitor monitor = monitor(aggregator);

        long before = System.currentTimeMillis();
        monitor.start();
        monitor.start();

        assertThat(monitor.snapshot()).isSameAs(first);
        assertThat(monitor.snapshot()).isSameAs(first);
        assertThat(aggregator.calls()).isEqualTo(1);

        ArgumentCaptor<Runnable> task = ArgumentCaptor.forClass(Runnable.class);
        ArgumentCaptor<Date> startsAt = ArgumentCaptor.forClass(Date.class);
        verify(scheduler).scheduleWithFixedDelay(task.capture(), startsAt.capture(), eq(1800000L));
        assertThat(startsAt.getValue().getTime()).isGreaterThanOrEqualTo(before + 1800000L);

        aggregator.enqueueImmediate(second);
        task.getValue().run();
        assertThat(monitor.snapshot()).isSameAs(second);
        assertThat(aggregator.calls()).isEqualTo(2);

        monitor.stop();
        verify(future).cancel(false);
    }

    @Test
    void earlyBrowserReadAndStartupShareOneCheck() {
        ControlledAggregator aggregator = new ControlledAggregator();
        aggregator.enqueueImmediate(first);
        ServiceHealthMonitor monitor = monitor(aggregator);

        assertThat(monitor.snapshot()).isSameAs(first);
        monitor.start();

        assertThat(monitor.snapshot()).isSameAs(first);
        assertThat(aggregator.calls()).isEqualTo(1);
        verify(scheduler, times(1))
                .scheduleWithFixedDelay(any(Runnable.class), any(Date.class), eq(1800000L));
    }

    @Test
    void keepsPreviousSnapshotIfScheduledCheckFails() {
        ControlledAggregator aggregator = new ControlledAggregator();
        aggregator.enqueueImmediate(first);
        ServiceHealthMonitor monitor = monitor(aggregator);
        monitor.start();

        Runnable task = scheduledTask();
        aggregator.enqueueFailure(new IllegalStateException("private-detail"));
        task.run();

        assertThat(monitor.snapshot()).isSameAs(first);
        assertThat(aggregator.calls()).isEqualTo(2);
        assertThat(aggregator.unexpectedCalls()).isZero();
    }

    @Test
    void testsCanDisableBackgroundChecks() {
        properties.setScheduledEnabled(false);
        ControlledAggregator aggregator = new ControlledAggregator();

        new ServiceHealthMonitor(aggregator, properties, scheduler).start();

        assertThat(aggregator.calls()).isZero();
        verifyNoInteractions(scheduler);
    }

    @Test
    void cachedSnapshotIsReadableWhileRefreshProbeRuns() throws Exception {
        ControlledAggregator aggregator = new ControlledAggregator();
        aggregator.enqueueImmediate(first);
        ServiceHealthMonitor monitor = monitor(aggregator);
        monitor.start();

        Probe slowRefresh = aggregator.enqueue(second);
        executor = Executors.newSingleThreadExecutor();
        Future<?> refresh = executor.submit(scheduledTask());
        assertThat(slowRefresh.awaitEntered()).isTrue();

        try {
            ServiceHealthSummary cached = CompletableFuture
                    .supplyAsync(monitor::snapshot)
                    .get(2, TimeUnit.SECONDS);
            assertThat(cached).isSameAs(first);
            assertThat(refresh.isDone()).isFalse();
        } finally {
            slowRefresh.release();
        }

        refresh.get(TIMEOUT_SECONDS, TimeUnit.SECONDS);
        assertThat(monitor.snapshot()).isSameAs(second);
        assertThat(aggregator.maxConcurrentProbes()).isEqualTo(1);
        assertThat(aggregator.unexpectedCalls()).isZero();
    }

    @Test
    void concurrentFirstReadsShareOneSlowProbe() throws Exception {
        ControlledAggregator aggregator = new ControlledAggregator();
        Probe slowProbe = aggregator.enqueue(first);
        ServiceHealthMonitor monitor = monitor(aggregator);

        int readers = 8;
        executor = Executors.newFixedThreadPool(readers);
        CountDownLatch ready = new CountDownLatch(readers);
        CountDownLatch go = new CountDownLatch(1);
        List<Future<ServiceHealthSummary>> results = new ArrayList<>();
        for (int i = 0; i < readers; i++) {
            results.add(executor.submit(() -> {
                ready.countDown();
                if (!go.await(TIMEOUT_SECONDS, TimeUnit.SECONDS)) {
                    throw new IllegalStateException("readers did not start");
                }
                return monitor.snapshot();
            }));
        }

        assertThat(ready.await(TIMEOUT_SECONDS, TimeUnit.SECONDS)).isTrue();
        go.countDown();
        try {
            assertThat(slowProbe.awaitEntered()).isTrue();
        } finally {
            slowProbe.release();
        }

        for (Future<ServiceHealthSummary> result : results) {
            assertThat(result.get(TIMEOUT_SECONDS, TimeUnit.SECONDS)).isSameAs(first);
        }
        assertThat(aggregator.calls()).isEqualTo(1);
        assertThat(aggregator.unexpectedCalls()).isZero();
    }

    @Test
    void concurrentRefreshCallbacksNeverRunTwoProbesAtOnce() throws Exception {
        ControlledAggregator aggregator = new ControlledAggregator();
        aggregator.enqueueImmediate(first);
        ServiceHealthMonitor monitor = monitor(aggregator);
        monitor.start();
        Runnable task = scheduledTask();

        Probe runningProbe = aggregator.enqueue(second);
        Probe secondProbe = aggregator.enqueue(third);

        executor = Executors.newFixedThreadPool(2);
        CountDownLatch ready = new CountDownLatch(2);
        CountDownLatch go = new CountDownLatch(1);
        Callable<Void> callback = () -> {
            ready.countDown();
            if (!go.await(TIMEOUT_SECONDS, TimeUnit.SECONDS)) {
                throw new IllegalStateException("refresh callbacks did not start");
            }
            task.run();
            return null;
        };
        Future<Void> firstCallback = executor.submit(callback);
        Future<Void> secondCallback = executor.submit(callback);

        assertThat(ready.await(TIMEOUT_SECONDS, TimeUnit.SECONDS)).isTrue();
        go.countDown();
        assertThat(runningProbe.awaitEntered()).isTrue();
        try {
            // 第二个回调应复用正在执行的探测，而不是再发起一个。
            assertThat(secondProbe.awaitEntered(250, TimeUnit.MILLISECONDS)).isFalse();
        } finally {
            runningProbe.release();
            secondProbe.release();
        }

        firstCallback.get(TIMEOUT_SECONDS, TimeUnit.SECONDS);
        secondCallback.get(TIMEOUT_SECONDS, TimeUnit.SECONDS);
        assertThat(aggregator.maxConcurrentProbes()).isEqualTo(1);
        assertThat(aggregator.unexpectedCalls()).isZero();
    }

    /**
     * 造一个调度器已被打桩的 monitor。
     *
     * <p>{@code scheduleWithFixedDelay} 返回 mock 的 {@link ScheduledFuture}，
     * 这样 {@code stop()} 里的 cancel 可以验证；间隔固定为 30 分钟，与生产配置一致。</p>
     */
    private ServiceHealthMonitor monitor(ServiceHealthAggregator aggregator) {
        doReturn(future).when(scheduler)
                .scheduleWithFixedDelay(any(Runnable.class), any(Date.class), eq(1800000L));
        return new ServiceHealthMonitor(aggregator, properties, scheduler);
    }

    /**
     * 从 mock 调度器里取出已注册的定时回调。
     *
     * <p>测试线程直接调用它，等价于「30 分钟到了、调度器触发了一次」；
     * 既不真实等待，也不会引入额外的调度线程干扰并发断言。</p>
     */
    private Runnable scheduledTask() {
        ArgumentCaptor<Runnable> task = ArgumentCaptor.forClass(Runnable.class);
        verify(scheduler).scheduleWithFixedDelay(task.capture(), any(Date.class), eq(1800000L));
        return task.getValue();
    }

    /**
     * 受控的慢健康服务：每次探测先占用一个槽位并等待测试释放，用来观察并发与阻塞。
     * 不发起任何网络请求。
     *
     * <p>同时记录三类计数：{@code calls} 总调用次数、{@code maxActive} 峰值并发数
     * （应始终为 1）、{@code unexpected} 没有排到 probe 却仍被调用的次数（正常应为 0）。
     * probe 队列按调用顺序消费，因此可以用排队顺序精确表达「第 n 次探测返回什么」。</p>
     */
    private static final class ControlledAggregator extends ServiceHealthAggregator {

        private final BlockingQueue<Probe> probes = new LinkedBlockingQueue<>();
        private final AtomicInteger calls = new AtomicInteger();
        private final AtomicInteger active = new AtomicInteger();
        private final AtomicInteger maxActive = new AtomicInteger();
        private final AtomicInteger unexpected = new AtomicInteger();

        private ControlledAggregator() {
            // checkAll 已重写，父类的 checker 和 executor 不会参与探测。
            super(new ServiceHealthProperties(), null, Runnable::run);
        }

        /** 排队一次需要测试手动放行的探测。 */
        private Probe enqueue(ServiceHealthSummary summary) {
            Probe probe = new Probe(summary, null);
            probes.add(probe);
            return probe;
        }

        /** 排队一次立即返回的探测，用于启动巡检这类不关心阻塞的用例。 */
        private Probe enqueueImmediate(ServiceHealthSummary summary) {
            Probe probe = new Probe(summary, null);
            probe.completeNow();
            probes.add(probe);
            return probe;
        }

        /** 排队一次立即失败的探测，用来模拟聚合器抛异常。 */
        private Probe enqueueFailure(RuntimeException failure) {
            Probe probe = new Probe(null, failure);
            probe.completeNow();
            probes.add(probe);
            return probe;
        }

        private int calls() {
            return calls.get();
        }

        private int maxConcurrentProbes() {
            return maxActive.get();
        }

        /** 没有排到 probe 却仍被调用的次数；任何用例里都应该保持 0。 */
        private int unexpectedCalls() {
            return unexpected.get();
        }

        @Override
        public ServiceHealthSummary checkAll() {
            calls.incrementAndGet();
            maxActive.accumulateAndGet(active.incrementAndGet(), Math::max);
            try {
                Probe probe = probes.poll();
                if (probe == null) {
                    unexpected.incrementAndGet();
                    return new ServiceHealthSummary(false, false, Collections.emptyList());
                }
                probe.entered.countDown();
                if (!probe.release.await(TIMEOUT_SECONDS, TimeUnit.SECONDS)) {
                    throw new IllegalStateException("controlled probe was not released");
                }
                if (probe.failure != null) {
                    throw probe.failure;
                }
                return probe.summary;
            } catch (InterruptedException exception) {
                Thread.currentThread().interrupt();
                throw new IllegalStateException("controlled probe interrupted", exception);
            } finally {
                active.decrementAndGet();
            }
        }
    }

    /**
     * 一次受控探测：{@code entered} 表示 {@code checkAll} 已进入，{@code release} 放行返回。
     *
     * <p>{@code failure} 非空时在放行后抛出，用来模拟聚合器异常；
     * {@code completeNow()} 供不希望阻塞的用例直接放行。</p>
     */
    private static final class Probe {

        private final ServiceHealthSummary summary;
        private final RuntimeException failure;
        private final CountDownLatch entered = new CountDownLatch(1);
        private final CountDownLatch release = new CountDownLatch(1);

        private Probe(ServiceHealthSummary summary, RuntimeException failure) {
            this.summary = summary;
            this.failure = failure;
        }

        private void completeNow() {
            release.countDown();
        }

        private void release() {
            release.countDown();
        }

        private boolean awaitEntered() throws InterruptedException {
            return entered.await(TIMEOUT_SECONDS, TimeUnit.SECONDS);
        }

        private boolean awaitEntered(long timeout, TimeUnit unit) throws InterruptedException {
            return entered.await(timeout, unit);
        }
    }
}
