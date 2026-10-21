package com.example.website.integration.models;

import org.junit.jupiter.api.*;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.*;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import com.example.website.integration.local.LocalServicesManager;
import java.util.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class ModelRoutingControllerTest {
    MockMvc mvc; ModelRoutingService service;
    @BeforeEach void setup(){service=mock(ModelRoutingService.class);when(service.catalog(false)).thenReturn(Collections.singletonMap("success",true));mvc=MockMvcBuilders.standaloneSetup(new ModelRoutingController(service,mock(LocalServicesManager.class))).build();}
    @Test void localServiceOriginsAreAllowedAndUnknownOriginsRejected()throws Exception {
        mvc.perform(get("/api/models").header("Origin","http://localhost:5177")).andExpect(status().isOk()).andExpect(header().string("Access-Control-Allow-Origin","http://localhost:5177"));
        mvc.perform(get("/api/models").header("Origin","https://evil.example")).andExpect(status().isForbidden());
        mvc.perform(get("/api/models").header("Origin","http://localhost:9998")).andExpect(status().isForbidden());
        mvc.perform(get("/api/models").with(r->{r.setRemoteAddr("192.0.2.3");return r;})).andExpect(status().isForbidden());
        mvc.perform(get("/api/models").with(r->{r.setServerName("evil.example");return r;})).andExpect(status().isForbidden());
    }
    @Test void writeRequiresCustomHeaderAndBrowserCannotGenerate()throws Exception {
        mvc.perform(put("/api/models/selection/global").contentType(MediaType.APPLICATION_JSON).content("{\"modelId\":\"\"}")).andExpect(status().isForbidden());
        mvc.perform(post("/api/models/chat/python-a").header("Origin","http://localhost:5174").header("X-Love530-Model","1").contentType(MediaType.APPLICATION_JSON).content("{}")).andExpect(status().isForbidden());
        verify(service,never()).chat(anyString(),any());
    }
    @Test void preflightFromServiceAllowsOnlyExpectedHeaders()throws Exception {
        mvc.perform(options("/api/models/selection/python-a").header("Origin","http://127.0.0.1:5174")).andExpect(status().isNoContent()).andExpect(header().string("Access-Control-Allow-Headers","Content-Type, X-Love530-Model"));
    }
    @Test void completeReturns204OnlyForNativeAndRejectsBrowserGeneration()throws Exception {
        mvc.perform(post("/api/models/complete/python-a").header("X-Love530-Model","1")
                .contentType(MediaType.APPLICATION_JSON).content("{}"))
                .andExpect(status().isNoContent()).andExpect(content().string(""));
        when(service.complete(eq("python-a"),any())).thenReturn(new com.fasterxml.jackson.databind.ObjectMapper().readTree("{\"model\":\"selected\"}"));
        mvc.perform(post("/api/models/complete/python-a").header("X-Love530-Model","1")
                .contentType(MediaType.APPLICATION_JSON).content("{}"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.model").value("selected"));
        clearInvocations(service);
        mvc.perform(post("/api/models/complete/python-a").header("Origin","http://localhost:5174")
                .header("X-Love530-Model","1").contentType(MediaType.APPLICATION_JSON).content("{}"))
                .andExpect(status().isForbidden());
        mvc.perform(post("/api/models/complete/python-a").contentType(MediaType.APPLICATION_JSON).content("{}"))
                .andExpect(status().isForbidden());
        verify(service,never()).complete(anyString(),any());
    }
}
