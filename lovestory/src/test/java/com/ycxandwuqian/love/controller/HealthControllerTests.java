package com.ycxandwuqian.love.controller;

import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * {@link HealthController} 的切片测试。
 *
 * <p>用 {@code MockMvcBuilders.standaloneSetup} 只装配该控制器，不启动 Spring 上下文、
 * 不连数据库也不碰 OSS。断言 {@code /api/health} 的 HTTP 状态、JSON 媒体类型，
 * 以及被 {@code website} 聚合依赖的两个契约字段：{@code success=true} 与
 * {@code service=lovestory}。</p>
 */
class HealthControllerTests {

    @Test
    void healthEndpointReturnsUnifiedServiceStatus() throws Exception {
        MockMvc mockMvc = MockMvcBuilders.standaloneSetup(new HealthController()).build();

        mockMvc.perform(get("/api/health"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith("application/json"))
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.service").value("lovestory"));
    }
}
