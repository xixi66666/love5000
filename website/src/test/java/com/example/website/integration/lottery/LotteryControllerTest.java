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
