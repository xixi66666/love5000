package com.example.website.integration.local;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.io.File;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

/**
 * {@link LocalServicesManager} 的单元测试。
 *
 * <p>被测对象管理三个本机应用：Strata（9999，Qwen 本地模型）、AIMedia 操作台（8190）与
 * H3 的 ComfyUI 引擎（8189）。本类用 mock 的 {@link LocalServiceClient} 与
 * {@link LocalServiceProcessRunner} 替代真实 HTTP 与进程启动，因此不会加载模型、不会生成视频，
 * 也不会留下子进程。</p>
 *
 * <p>固定的关键规则：</p>
 * <ul>
 *   <li>「服务在线」与「模型已加载」是两件事：Strata 在线但 {@code loaded=false} 时运行状态为真、
 *       模型状态为假；</li>
 *   <li>已在线则复用，不重复启动；{@code start} 只传 {@code --lazy}，不顺手打开浏览器；</li>
 *   <li>只有 Strata 支持 {@code load}，AIMedia 不支持 {@code unload}；未知服务 404、未知操作 400；</li>
 *   <li>忙碌（队列或操作台作业未完成，或上游直接返回 409）时拒绝卸载与停止；
 *       读不到队列时按 503 失败关闭，宁可不操作也不误杀任务；</li>
 *   <li>H3 空闲时 {@code unload} 只调 {@code /free} 释放显存，引擎继续在线；</li>
 *   <li>启动命令复用已装好的 {@code ComfyUI/.venv-rocm} 解释器并带真实端口，不自动拉起浏览器。</li>
 * </ul>
 */
class LocalServicesManagerTest {
    private final LocalServiceProperties properties = new LocalServiceProperties();
    private final LocalServiceClient client = mock(LocalServiceClient.class);
    private final LocalServiceProcessRunner runner = mock(LocalServiceProcessRunner.class);
    private final LocalServicesManager manager = new LocalServicesManager(properties, client, runner);
    private final ObjectMapper mapper = new ObjectMapper();

    @Test
    void distinguishesRunningServiceFromUnloadedModel() throws Exception {
        when(client.get(9999, "/health")).thenReturn(json("{\"service\":\"strata\",\"loaded\":false}"));
        Map<String, Object> status = manager.status("strata");
        assertEquals(true, status.get("running"));
        assertEquals(false, status.get("loaded"));
        verifyNoInteractions(runner);
    }

    @Test
    void reusesExistingServiceWithoutStartingAnotherProcess() throws Exception {
        when(client.get(8190, "/api/status")).thenReturn(json("{\"app\":\"AIMedia Studio\"}"));
        assertEquals(true, manager.action("aimedia", "start").get("running"));
        verifyNoInteractions(runner);
    }

    @Test
    void startsServiceWithLazyModelAndWaitsForMatchingHealth() throws Exception {
        when(client.get(9999, "/health")).thenReturn(null, json("{\"service\":\"strata\",\"loaded\":false}"));
        when(runner.start(any(File.class), anyList())).thenReturn(mock(Process.class));
        assertEquals(false, manager.action("strata", "start").get("loaded"));
        verify(runner).start(any(File.class), argThat(command -> command.contains("--lazy") && !command.contains("--open")));
        verify(client, never()).post(anyInt(), eq("/load"), anyString(), anyInt());
    }

    @Test
    void explicitLoadCallsTheModelEndpoint() throws Exception {
        when(client.get(9999, "/health")).thenReturn(json("{\"service\":\"strata\",\"loaded\":true}"));
        manager.action("strata", "load");
        verify(client).post(9999, "/load", "{}", 180000);
    }

    @Test
    void busyModelCannotBeStopped() throws Exception {
        when(client.get(9999, "/health")).thenReturn(json("{\"service\":\"strata\",\"loaded\":true}"));
        when(client.post(eq(9999), eq("/unload"), anyString(), anyInt()))
                .thenThrow(new LocalServiceException(409, "busy"));
        assertEquals(409, assertThrows(LocalServiceException.class, () -> manager.action("strata", "stop")).getStatus());
        verifyNoInteractions(runner);
    }

    @Test
    void pendingVideoPreventsBothReleaseAndStop() throws Exception {
        when(client.get(8189, "/system_stats")).thenReturn(json("{\"system\":{},\"devices\":[]}"));
        when(client.get(8189, "/queue")).thenReturn(json("{\"queue_running\":[],\"queue_pending\":[[1]]}"));
        for (String action : new String[] {"unload", "stop"}) {
            assertEquals(409, assertThrows(LocalServiceException.class, () -> manager.action("h3", action)).getStatus());
        }
        verify(client, never()).post(anyInt(), anyString(), anyString(), anyInt());
        verifyNoInteractions(runner);
    }

    @Test
    void releaseFailsClosedWhenQueueCannotBeRead() throws Exception {
        when(client.get(8189, "/system_stats")).thenReturn(json("{\"system\":{},\"devices\":[]}"));
        assertEquals(503, assertThrows(LocalServiceException.class, () -> manager.action("h3", "unload")).getStatus());
        verify(client, never()).post(anyInt(), anyString(), anyString(), anyInt());
    }

    @Test
    void idleVideoCanReleaseModelsWithoutStoppingTheEngine() throws Exception {
        when(client.get(8189, "/system_stats")).thenReturn(json("{\"system\":{},\"devices\":[]}"));
        when(client.get(8189, "/queue")).thenReturn(json("{\"queue_running\":[],\"queue_pending\":[]}"));
        assertEquals(true, manager.action("h3", "unload").get("running"));
        verify(client).post(8189, "/free", "{\"unload_models\":true,\"free_memory\":true}", 180000);
        verifyNoInteractions(runner);
    }

    @Test
    void studioJobPreventsStoppingEvenWhenGpuQueueIsEmpty() throws Exception {
        when(client.get(8190, "/api/status")).thenReturn(json("{\"app\":\"AIMedia Studio\"}"));
        when(client.get(8190, "/api/jobs")).thenReturn(json("{\"jobs\":[{\"status\":\"running\"}]}"));
        assertEquals(409, assertThrows(LocalServiceException.class, () -> manager.action("aimedia", "stop")).getStatus());
        verifyNoInteractions(runner);
    }

    @Test
    void rejectsUnknownServicesAndUnsupportedActions() {
        assertEquals(404, assertThrows(LocalServiceException.class, () -> manager.action("other", "start")).getStatus());
        assertEquals(400, assertThrows(LocalServiceException.class, () -> manager.action("strata", "execute")).getStatus());
        assertEquals(400, assertThrows(LocalServiceException.class, () -> manager.action("h3", "load")).getStatus());
        verifyNoInteractions(runner, client);
    }

    @Test
    void foreignServiceDoesNotCountAsAHealthyStrataInstance() throws Exception {
        when(client.get(9999, "/health")).thenReturn(json("{\"success\":true,\"service\":\"another-app\"}"));
        assertEquals(false, manager.status("strata").get("running"));
    }

    @Test
    void videoCommandsUseTheExistingGpuEnvironmentAndActualEnginePort() {
        // 必须复用已装好的 ROCm 虚拟环境、带上真实引擎端口，并且不额外拉起浏览器进程。
        List<String> command = manager.command("h3");
        assertTrue(command.get(0).replace('\\', '/').endsWith("ComfyUI/.venv-rocm/Scripts/python.exe"));
        assertTrue(command.contains("8189"));
        assertTrue(command.contains("--reserve-vram"));
        assertFalse(command.contains("--auto-launch"));
    }

    /** 把测试内联的 JSON 字面量解析成 {@link JsonNode}，用来模拟本机应用返回的状态体。 */
    private JsonNode json(String source) throws Exception { return mapper.readTree(source); }
}
