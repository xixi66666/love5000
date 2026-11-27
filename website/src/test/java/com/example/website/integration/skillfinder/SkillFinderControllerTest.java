package com.example.website.integration.skillfinder;

import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * {@link SkillFinderController} 的 Web 层测试：standalone MockMvc 加 mock 的
 * {@link SkillFinderProcessManager}，不启动 Python、不连接 5177，也不访问与 website
 * 共用的 MySQL。
 *
 * <p>固定首页卡片依赖的响应契约：启动成功返回 200、{@code success=true}、
 * {@code status=started} 与可打开的 url；已在线时 {@code status=already-running}；
 * 失败返回 503、{@code success=false} 与可读 {@code message}（例如前端未构建）；
 * 状态接口只读 manager。</p>
 */
class SkillFinderControllerTest {

    @Test
    void startsServiceAndReturnsUrl() throws Exception {
        SkillFinderProcessManager manager = mock(SkillFinderProcessManager.class);
        when(manager.start()).thenReturn(
                new SkillFinderStartResult(SkillFinderStartResult.STATUS_STARTED, "http://127.0.0.1:5177/"));
        MockMvc mockMvc = MockMvcBuilders
                .standaloneSetup(new SkillFinderController(manager))
                .build();

        mockMvc.perform(post("/api/services/skill-finder/start"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.status").value("started"))
                .andExpect(jsonPath("$.url").value("http://127.0.0.1:5177/"));
    }

    @Test
    void reusesAlreadyRunningService() throws Exception {
        SkillFinderProcessManager manager = mock(SkillFinderProcessManager.class);
        when(manager.start()).thenReturn(
                new SkillFinderStartResult(SkillFinderStartResult.STATUS_ALREADY_RUNNING, "http://127.0.0.1:5177/"));
        MockMvc mockMvc = MockMvcBuilders
                .standaloneSetup(new SkillFinderController(manager))
                .build();

        mockMvc.perform(post("/api/services/skill-finder/start"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.status").value("already-running"));
    }

    @Test
    void returnsServiceUnavailableWithMessageWhenStartFails() throws Exception {
        SkillFinderProcessManager manager = mock(SkillFinderProcessManager.class);
        when(manager.start()).thenThrow(new SkillFinderStartException("skill-finder 前端尚未构建"));
        MockMvc mockMvc = MockMvcBuilders
                .standaloneSetup(new SkillFinderController(manager))
                .build();

        mockMvc.perform(post("/api/services/skill-finder/start"))
                .andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value("skill-finder 前端尚未构建"));
    }

    @Test
    void reportsCurrentStatus() throws Exception {
        SkillFinderProcessManager manager = mock(SkillFinderProcessManager.class);
        when(manager.isRunning()).thenReturn(true);
        when(manager.appUrl()).thenReturn("http://127.0.0.1:5177/");
        MockMvc mockMvc = MockMvcBuilders
                .standaloneSetup(new SkillFinderController(manager))
                .build();

        mockMvc.perform(get("/api/services/skill-finder/status"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.running").value(true))
                .andExpect(jsonPath("$.url").value("http://127.0.0.1:5177/"));
    }
}
