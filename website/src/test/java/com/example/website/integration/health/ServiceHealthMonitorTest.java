package com.example.website.integration.health;

import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.scheduling.TaskScheduler;

import java.util.Collections;
import java.util.Date;
import java.util.concurrent.ScheduledFuture;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.*;

class ServiceHealthMonitorTest {

    private final ServiceHealthAggregator aggregator = mock(ServiceHealthAggregator.class);
    private final TaskScheduler scheduler = mock(TaskScheduler.class);
    private final ScheduledFuture<?> future = mock(ScheduledFuture.class);
    private final ServiceHealthProperties properties = new ServiceHealthProperties();
    private final ServiceHealthSummary first = new ServiceHealthSummary(true, true, Collections.emptyList());

    private ServiceHealthMonitor monitor() {
        when(aggregator.checkAll()).thenReturn(first);
        doReturn(future).when(scheduler).scheduleWithFixedDelay(any(Runnable.class), any(Date.class), eq(1800000L));
        return new ServiceHealthMonitor(aggregator, properties, scheduler);
    }

    @Test
    void checksOnceAtStartupAndSchedulesNextCheckThirtyMinutesLater() {
        ServiceHealthMonitor monitor = monitor();
        long before = System.currentTimeMillis();
        monitor.start();
        monitor.start();
        assertThat(monitor.snapshot()).isSameAs(first);
        assertThat(monitor.snapshot()).isSameAs(first);
        verify(aggregator, times(1)).checkAll();
        ArgumentCaptor<Runnable> task = ArgumentCaptor.forClass(Runnable.class);
        ArgumentCaptor<Date> startsAt = ArgumentCaptor.forClass(Date.class);
        verify(scheduler).scheduleWithFixedDelay(task.capture(), startsAt.capture(), eq(1800000L));
        assertThat(startsAt.getValue().getTime()).isGreaterThanOrEqualTo(before + 1800000L);

        ServiceHealthSummary second = new ServiceHealthSummary(true, false, Collections.emptyList());
        when(aggregator.checkAll()).thenReturn(second);
        task.getValue().run();
        assertThat(monitor.snapshot()).isSameAs(second);
        verify(aggregator, times(2)).checkAll();
        monitor.stop();
        verify(future).cancel(false);
    }

    @Test
    void earlyBrowserReadAndStartupShareOneCheck() {
        ServiceHealthMonitor monitor = monitor();
        assertThat(monitor.snapshot()).isSameAs(first);
        monitor.start();
        verify(aggregator, times(1)).checkAll();
    }

    @Test
    void keepsPreviousSnapshotIfScheduledCheckFails() {
        ServiceHealthMonitor monitor = monitor();
        monitor.start();
        ArgumentCaptor<Runnable> task = ArgumentCaptor.forClass(Runnable.class);
        verify(scheduler).scheduleWithFixedDelay(task.capture(), any(Date.class), eq(1800000L));
        when(aggregator.checkAll()).thenThrow(new IllegalStateException("private-detail"));
        task.getValue().run();
        assertThat(monitor.snapshot()).isSameAs(first);
    }

    @Test
    void testsCanDisableBackgroundChecks() {
        properties.setScheduledEnabled(false);
        new ServiceHealthMonitor(aggregator, properties, scheduler).start();
        verifyNoInteractions(aggregator, scheduler);
    }
}
