package com.example.website.integration.local;

import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.util.HashMap;
import java.util.Map;

import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * {@link LocalServicesController} 的 Web 层测试：standalone MockMvc 加 mock 的
 * {@link LocalServicesManager}，不加载本机模型、不生成视频、不访问真实端口。
 *
 * <p>本类固定两条边界。第一条是「谁能操作本机服务」：回环地址、本机 Host、同源 Origin 齐全时
 * 才放行，只改 Origin、只改 Host 或缺少 {@code X-Love530-Local} 都返回 403，而且根本不调用
 * manager。第二条是「失败如何呈现」：离线健康检查返回 503 且 {@code success=false}，不能
 * 谎报为 HTTP 成功；manager 抛出的 409 原样映射为 HTTP 409 与 {@code success=false}，
 * 页面据此提示任务仍在运行。</p>
 */
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

    /**
     * 构造 {@code manager.status()} 的返回体。
     *
     * <p>{@code /health} 端点依据 {@code running} 决定返回 200 还是 503，因此这里必须是真实布尔值，
     * 不能写死。</p>
     *
     * @param running 服务当前是否在线
     * @return 含 {@code success=true} 与 {@code running} 的状态快照
     */
    private Map<String, Object> state(boolean running) {
        Map<String, Object> state = new HashMap<>();
        state.put("success", true);
        state.put("running", running);
        return state;
    }
}
