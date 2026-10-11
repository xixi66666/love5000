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
        List<String> command = manager.command("h3");
        assertTrue(command.get(0).replace('\\', '/').endsWith("ComfyUI/.venv-rocm/Scripts/python.exe"));
        assertTrue(command.contains("8189"));
        assertTrue(command.contains("--reserve-vram"));
        assertFalse(command.contains("--auto-launch"));
    }

    private JsonNode json(String source) throws Exception { return mapper.readTree(source); }
}
