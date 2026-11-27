package com.example.website.integration.lottery;

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
 * {@link LotteryController} 的 Web 层测试：standalone MockMvc 加 mock 的
 * {@link LotteryProcessManager}，不启动 Python、不连接 5179。
 *
 * <p>固定首页卡片依赖的响应契约：首次启动返回 200、{@code success=true}、
 * {@code status=started} 与可直接打开的 url；已在线时返回 200 与
 * {@code status=already-running}，页面据此提示「点击打开」；启动失败返回 503、
 * {@code success=false}，并把可读原因原样放进 {@code message}；状态接口只读 manager。</p>
 */
class LotteryControllerTest {

    @Test
    void startsServiceAndReturnsUrl() throws Exception {
        LotteryProcessManager manager = mock(LotteryProcessManager.class);
        when(manager.start()).thenReturn(
                new LotteryStartResult(LotteryStartResult.STATUS_STARTED, "http://127.0.0.1:5179/"));
        MockMvc mockMvc = MockMvcBuilders
                .standaloneSetup(new LotteryController(manager))
                .build();

        mockMvc.perform(post("/api/services/lottery/start"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.status").value("started"))
                .andExpect(jsonPath("$.url").value("http://127.0.0.1:5179/"));
    }

    @Test
    void reusesAlreadyRunningService() throws Exception {
        LotteryProcessManager manager = mock(LotteryProcessManager.class);
        when(manager.start()).thenReturn(
                new LotteryStartResult(LotteryStartResult.STATUS_ALREADY_RUNNING, "http://127.0.0.1:5179/"));
        MockMvc mockMvc = MockMvcBuilders
                .standaloneSetup(new LotteryController(manager))
                .build();

        mockMvc.perform(post("/api/services/lottery/start"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.status").value("already-running"));
    }

    @Test
    void returnsServiceUnavailableWithMessageWhenStartFails() throws Exception {
        LotteryProcessManager manager = mock(LotteryProcessManager.class);
        when(manager.start()).thenThrow(new LotteryStartException("开奖数据操作台缺少 server.py"));
        MockMvc mockMvc = MockMvcBuilders
                .standaloneSetup(new LotteryController(manager))
                .build();

        mockMvc.perform(post("/api/services/lottery/start"))
                .andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value("开奖数据操作台缺少 server.py"));
    }

    @Test
    void reportsCurrentStatus() throws Exception {
        LotteryProcessManager manager = mock(LotteryProcessManager.class);
        when(manager.isRunning()).thenReturn(true);
        when(manager.appUrl()).thenReturn("http://127.0.0.1:5179/");
        MockMvc mockMvc = MockMvcBuilders
                .standaloneSetup(new LotteryController(manager))
                .build();

        mockMvc.perform(get("/api/services/lottery/status"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.running").value(true))
                .andExpect(jsonPath("$.url").value("http://127.0.0.1:5179/"));
    }
}
