package com.example.website.integration.health;

import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.util.Arrays;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * 聚合健康接口 {@code GET /api/services/health} 的 MVC 契约测试。
 *
 * <p>用 standalone MockMvc 只装配 {@link ServiceHealthController}，{@link ServiceHealthMonitor}
 * 由 Mockito mock 固定返回一个「一项在线、一项离线」的快照。断言的核心是一条容易误读的语义：
 * 即使有目标离线，HTTP 状态仍是 200 且 {@code success=true}（表示本轮汇总已经生成），
 * 是否全部在线由 {@code healthy=false} 表达；同时校验 services 数组保持聚合顺序、
 * {@code statusCode} 缺省时序列化为空、健康项没有 {@code message}。</p>
 *
 * <p>隔离：{@code standaloneSetup} 不加载 Spring 上下文、不建数据源、不触发真实探测，
 * 因此这里只验证响应形状。首页每半小时只读这份快照，字段改名会先在这里失败。</p>
 */
class ServiceHealthControllerTest {

    @Test
    void returnsAggregateHealthDetailsWithHttpTwoHundred() throws Exception {
        ServiceHealthDefinition imagetemplate = new ServiceHealthDefinition(
                "imagetemplate", "http://127.0.0.1:8082/api/health");
        ServiceHealthDefinition pythona = new ServiceHealthDefinition(
                "python-a", "http://127.0.0.1:5174/api/health");
        ServiceHealthSummary summary = new ServiceHealthSummary(
                true,
                false,
                Arrays.asList(
                        ServiceHealthResult.healthy(imagetemplate, 200, 12),
                        ServiceHealthResult.unhealthy(pythona, null, 7, "Connection failed")));
        ServiceHealthMonitor monitor = mock(ServiceHealthMonitor.class);
        when(monitor.snapshot()).thenReturn(summary);
        MockMvc mockMvc = MockMvcBuilders
                .standaloneSetup(new ServiceHealthController(monitor))
                .build();

        mockMvc.perform(get("/api/services/health"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.healthy").value(false))
                .andExpect(jsonPath("$.services[0].name").value("imagetemplate"))
                .andExpect(jsonPath("$.services[0].statusCode").value(200))
                .andExpect(jsonPath("$.services[0].message").isEmpty())
                .andExpect(jsonPath("$.services[1].name").value("python-a"))
                .andExpect(jsonPath("$.services[1].statusCode").isEmpty())
                .andExpect(jsonPath("$.services[1].message").value("Connection failed"));
    }
}
