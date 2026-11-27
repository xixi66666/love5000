package com.example.website.integration.personalagent;

import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * {@link PersonalAgentController} 的 Web 层测试：standalone MockMvc 加 mock 的
 * {@link PersonalAgentProcessManager}，不拉起 JVM、不监听 5178。
 *
 * <p>本类专门固定「谁可以点启动」。个人资料库承载本机私有资料，因此远程地址、非本机 Host、
 * 跨源 Origin 一律 403；Origin 的 scheme/host/port 必须与请求一致，所以
 * {@code http://localhost:8080}、{@code null}、带 path 或 query 的 Origin 全部拒绝；
 * 没有 Origin 时必须由 {@code Sec-Fetch-Site: same-origin} 证明同源，{@code same-site} 不够；
 * IPv6 回环 {@code [::1]} 与浏览器实际端口放行。</p>
 *
 * <p>另外固定两条契约：启动失败返回 503 与可读 {@code message}；状态接口只读，
 * 绝不触发启动。</p>
 */
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
        // MockMvc 默认 serverPort=80，Origin 却写 8080，端口不一致即视为跨源。
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
