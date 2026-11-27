package com.example.website.integration.scrapling;

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
 * {@link ScraplingUiController} 的 Web 层测试：standalone MockMvc 加 mock 的
 * {@link ScraplingUiProcessManager}，不启动 Python、不启动浏览器、不连接 5176。
 *
 * <p>固定首页卡片依赖的响应契约：启动成功返回 200、{@code success=true}、
 * {@code status=started} 与可打开的 url；已在线时 {@code status=already-running}；
 * 启动失败返回 503、{@code success=false} 与可读 {@code message}（例如前端未构建）；
 * 状态接口只读 manager。</p>
 */
class ScraplingUiControllerTest {

    @Test
    void startsServiceAndReturnsUrl() throws Exception {
        ScraplingUiProcessManager manager = mock(ScraplingUiProcessManager.class);
        when(manager.start()).thenReturn(
                new ScraplingUiStartResult(ScraplingUiStartResult.STATUS_STARTED, "http://127.0.0.1:5176/"));
        MockMvc mockMvc = MockMvcBuilders
                .standaloneSetup(new ScraplingUiController(manager))
                .build();

        mockMvc.perform(post("/api/services/scrapling-ui/start"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.status").value("started"))
                .andExpect(jsonPath("$.url").value("http://127.0.0.1:5176/"));
    }

    @Test
    void reusesAlreadyRunningService() throws Exception {
        ScraplingUiProcessManager manager = mock(ScraplingUiProcessManager.class);
        when(manager.start()).thenReturn(
                new ScraplingUiStartResult(ScraplingUiStartResult.STATUS_ALREADY_RUNNING, "http://127.0.0.1:5176/"));
        MockMvc mockMvc = MockMvcBuilders
                .standaloneSetup(new ScraplingUiController(manager))
                .build();

        mockMvc.perform(post("/api/services/scrapling-ui/start"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.status").value("already-running"));
    }

    @Test
    void returnsServiceUnavailableWithMessageWhenStartFails() throws Exception {
        ScraplingUiProcessManager manager = mock(ScraplingUiProcessManager.class);
        when(manager.start()).thenThrow(new ScraplingUiStartException("scrapling-ui 前端尚未构建"));
        MockMvc mockMvc = MockMvcBuilders
                .standaloneSetup(new ScraplingUiController(manager))
                .build();

        mockMvc.perform(post("/api/services/scrapling-ui/start"))
                .andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value("scrapling-ui 前端尚未构建"));
    }

    @Test
    void reportsCurrentStatus() throws Exception {
        ScraplingUiProcessManager manager = mock(ScraplingUiProcessManager.class);
        when(manager.isRunning()).thenReturn(true);
        when(manager.appUrl()).thenReturn("http://127.0.0.1:5176/");
        MockMvc mockMvc = MockMvcBuilders
                .standaloneSetup(new ScraplingUiController(manager))
                .build();

        mockMvc.perform(get("/api/services/scrapling-ui/status"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.running").value(true))
                .andExpect(jsonPath("$.url").value("http://127.0.0.1:5176/"));
    }
}
