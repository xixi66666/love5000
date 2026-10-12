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
