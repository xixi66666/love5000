package com.example.imagetemplate.controller;

import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * {@link HealthController} 的独立契约测试。
 *
 * <p>校验 {@code GET /api/health} 返回 HTTP 200、JSON 内容类型，以及固定结构
 * {@code success=true} 与 {@code service=imagetemplate}，供 website 的统一健康检查器识别。
 * 只校验固定字段，不涉及模板数据或图片生成配置。</p>
 *
 * <p>使用 {@code standaloneSetup} 仅装配该 Controller，不启动 Spring 上下文，也不触发任何
 * OpenAI 调用或文件读取。</p>
 */
class HealthControllerTest {

    @Test
    void healthEndpointReturnsUnifiedServiceStatus() throws Exception {
        MockMvc mockMvc = MockMvcBuilders.standaloneSetup(new HealthController()).build();

        mockMvc.perform(get("/api/health"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith("application/json"))
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.service").value("imagetemplate"));
    }
}
