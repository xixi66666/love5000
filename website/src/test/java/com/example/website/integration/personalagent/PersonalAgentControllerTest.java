package com.example.website.integration.personalagent;

import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class PersonalAgentControllerTest {

    private final PersonalAgentProcessManager manager = mock(PersonalAgentProcessManager.class);
    private final MockMvc mvc = MockMvcBuilders.standaloneSetup(new PersonalAgentController(manager)).build();

    @Test
    void startsFromSameOriginLocalBrowserWithoutAdditionalHeader() throws Exception {
        when(manager.start()).thenReturn(new PersonalAgentStartResult("started", "http://127.0.0.1:5178/"));

        mvc.perform(post("/api/services/personal-agent/start").header("Origin", "http://localhost")
                .header("Sec-Fetch-Site", "same-origin"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.status").value("started"))
                .andExpect(jsonPath("$.url").value("http://127.0.0.1:5178/"));
    }

    @Test
    void acceptsSameOriginFetchMetadataWhenOriginIsAbsent() throws Exception {
        when(manager.start()).thenReturn(new PersonalAgentStartResult("already-running", "http://127.0.0.1:5178/"));
        mvc.perform(post("/api/services/personal-agent/start").header("Sec-Fetch-Site", "same-origin"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.status").value("already-running"));
    }

    @Test
    void reportsSafeStartupFailure() throws Exception {
        when(manager.start()).thenThrow(new PersonalAgentStartException("个人 Agent 端口已被占用"));
        mvc.perform(post("/api/services/personal-agent/start").header("Origin", "http://localhost"))
                .andExpect(status().isServiceUnavailable()).andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value("个人 Agent 端口已被占用"));
    }

    @Test
    void reportsStatusWithoutStartingService() throws Exception {
        when(manager.isRunning()).thenReturn(true);
        when(manager.appUrl()).thenReturn("http://127.0.0.1:5178/");
        mvc.perform(get("/api/services/personal-agent/status"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.running").value(true))
                .andExpect(jsonPath("$.url").value("http://127.0.0.1:5178/"));
        verify(manager, never()).start();
    }

    @Test
    void rejectsRemoteAddressAndForeignHostWithoutCallingManager() throws Exception {
        mvc.perform(post("/api/services/personal-agent/start").header("Origin", "http://localhost")
                .with(request -> { request.setRemoteAddr("192.168.1.2"); return request; }))
                .andExpect(status().isForbidden());
        mvc.perform(get("/api/services/personal-agent/status")
                .with(request -> { request.setServerName("example.com"); return request; }))
                .andExpect(status().isForbidden());
        mvc.perform(post("/api/services/personal-agent/start").header("Origin", "http://localhost")
                .header("Host", "evil.example"))
                .andExpect(status().isForbidden());
        verifyNoInteractions(manager);
    }

    @Test
    void rejectsCrossOriginFetchSiteAndMissingOriginEvidence() throws Exception {
        mvc.perform(post("/api/services/personal-agent/start").header("Origin", "https://example.com"))
                .andExpect(status().isForbidden());
        mvc.perform(post("/api/services/personal-agent/start").header("Origin", "http://localhost")
                .header("Sec-Fetch-Site", "cross-site"))
                .andExpect(status().isForbidden());
        mvc.perform(post("/api/services/personal-agent/start").header("Sec-Fetch-Site", "same-site"))
                .andExpect(status().isForbidden());
        mvc.perform(post("/api/services/personal-agent/start"))
                .andExpect(status().isForbidden());
        verifyNoInteractions(manager);
    }

    @Test
    void validatesOriginPortAndRejectsMalformedOrigins() throws Exception {
        mvc.perform(post("/api/services/personal-agent/start").header("Origin", "http://localhost:8080"))
                .andExpect(status().isForbidden());
        mvc.perform(post("/api/services/personal-agent/start").header("Origin", "null"))
                .andExpect(status().isForbidden());
        mvc.perform(post("/api/services/personal-agent/start").header("Origin", "http://localhost/path"))
                .andExpect(status().isForbidden());
        mvc.perform(post("/api/services/personal-agent/start").header("Origin", "http://localhost?query"))
                .andExpect(status().isForbidden());
        verifyNoInteractions(manager);
    }

    @Test
    void acceptsIpv6LoopbackAndConfiguredBrowserPort() throws Exception {
        when(manager.start()).thenReturn(new PersonalAgentStartResult("started", "http://127.0.0.1:5178/"));
        mvc.perform(post("/api/services/personal-agent/start").header("Origin", "http://[::1]:8080")
                .header("Host", "[::1]:8080").with(request -> {
                    request.setRemoteAddr("::1");
                    request.setServerName("::1");
                    request.setServerPort(8080);
                    return request;
                })).andExpect(status().isOk());
    }
}
