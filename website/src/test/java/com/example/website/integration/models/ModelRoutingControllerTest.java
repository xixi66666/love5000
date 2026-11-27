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

/**
 * {@link ModelRoutingController} 的 Web 层测试。
 *
 * <p>standalone MockMvc 加 mock 的 {@link ModelRoutingService} 与
 * {@link LocalServicesManager}：不下发真实模型请求，也不操作本机进程。</p>
 *
 * <p>固定的边界是「控制器自带的本机校验比 CORS 声明更严格」：远程地址、非本机 Host、
 * 白名单之外的回环端口（例如 9998）一律 403；写操作必须带 {@code X-Love530-Model: 1}；
 * 带 {@code Origin} 说明请求来自浏览器，生成接口直接拒绝；{@code /complete} 用 204
 * 明确表示「使用服务原配置」，只有拿到结果时才返回 200 与 JSON。</p>
 */
class ModelRoutingControllerTest {
    MockMvc mvc; ModelRoutingService service;
    // 目录接口只需返回可序列化的 Map；鉴权与生成边界才是本类关注点。
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
    // 预检由控制器自己的 OPTIONS 处理器应答，允许头固定为 Content-Type 与 X-Love530-Model。
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
        // 清掉前面的调用记录，让最后的 never() 只针对「带 Origin 的浏览器请求」与「缺自定义头」。
        clearInvocations(service);
        mvc.perform(post("/api/models/complete/python-a").header("Origin","http://localhost:5174")
                .header("X-Love530-Model","1").contentType(MediaType.APPLICATION_JSON).content("{}"))
                .andExpect(status().isForbidden());
        mvc.perform(post("/api/models/complete/python-a").contentType(MediaType.APPLICATION_JSON).content("{}"))
                .andExpect(status().isForbidden());
        verify(service,never()).complete(anyString(),any());
    }
}
