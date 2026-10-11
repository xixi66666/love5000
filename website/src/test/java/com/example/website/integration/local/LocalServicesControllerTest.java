package com.example.website.integration.local;

import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.util.HashMap;
import java.util.Map;

import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class LocalServicesControllerTest {
    private final LocalServicesManager manager = mock(LocalServicesManager.class);
    private final MockMvc mvc = MockMvcBuilders.standaloneSetup(new LocalServicesController(manager)).build();

    @Test
    void acceptsSameOriginLocalControl() throws Exception {
        when(manager.action("strata", "start")).thenReturn(state(true));
        mvc.perform(post("/api/services/local/strata/start").header("X-Love530-Local", "1")
                .header("Origin", "http://localhost"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.success").value(true));
    }

    @Test
    void rejectsRemoteMachinesWithoutCallingProcessManagement() throws Exception {
        mvc.perform(post("/api/services/local/h3/stop").header("X-Love530-Local", "1")
                .with(request -> { request.setRemoteAddr("192.168.1.50"); return request; }))
                .andExpect(status().isForbidden());
        verifyNoInteractions(manager);
    }

    @Test
    void rejectsCrossOriginAndMissingControlHeader() throws Exception {
        mvc.perform(post("/api/services/local/strata/load").header("X-Love530-Local", "1")
                .header("Origin", "https://example.com")).andExpect(status().isForbidden());
        mvc.perform(post("/api/services/local/strata/load")).andExpect(status().isForbidden());
        verifyNoInteractions(manager);
    }

    @Test
    void rejectsForeignHostEvenOnALocalConnection() throws Exception {
        mvc.perform(get("/api/services/local/strata/status").with(request -> {
            request.setServerName("example.com"); return request;
        })).andExpect(status().isForbidden());
        verifyNoInteractions(manager);
    }

    @Test
    void offlineHealthIsNotReportedAsHttpSuccess() throws Exception {
        when(manager.status("strata")).thenReturn(state(false));
        mvc.perform(get("/api/services/local/strata/health")).andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("$.success").value(false));
    }

    @Test
    void returnsBusyWithoutPretendingTheOperationCompleted() throws Exception {
        when(manager.action("h3", "stop")).thenThrow(new LocalServiceException(409, "任务运行中"));
        mvc.perform(post("/api/services/local/h3/stop").header("X-Love530-Local", "1"))
                .andExpect(status().isConflict()).andExpect(jsonPath("$.success").value(false));
    }

    private Map<String, Object> state(boolean running) {
        Map<String, Object> state = new HashMap<>();
        state.put("success", true);
        state.put("running", running);
        return state;
    }
}
