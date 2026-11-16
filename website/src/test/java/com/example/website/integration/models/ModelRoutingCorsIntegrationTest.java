package com.example.website.integration.models;

import org.junit.jupiter.api.*;
import org.springframework.context.annotation.*;
import org.springframework.mock.web.MockServletContext;
import org.springframework.test.web.servlet.*;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.support.AnnotationConfigWebApplicationContext;
import org.springframework.web.servlet.config.annotation.EnableWebMvc;
import com.example.website.integration.local.LocalServicesManager;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/** 使用真实 MVC HandlerMapping 与预检适配器，避免仅测控制器手写 OPTIONS。 */
class ModelRoutingCorsIntegrationTest {
    AnnotationConfigWebApplicationContext context;
    MockMvc mvc;
    @Configuration
    @EnableWebMvc
    static class Config {
        @Bean ModelRoutingService modelRoutingService(){return mock(ModelRoutingService.class);}
        @Bean LocalServicesManager localServicesManager(){return mock(LocalServicesManager.class);}
        @Bean ModelRoutingController modelRoutingController(ModelRoutingService service,LocalServicesManager local){return new ModelRoutingController(service,local);}
    }
    @BeforeEach void setup(){
        context=new AnnotationConfigWebApplicationContext();context.setServletContext(new MockServletContext());
        context.register(Config.class);context.refresh();mvc=MockMvcBuilders.webAppContextSetup(context).build();
    }
    @AfterEach void close(){context.close();}
    @Test void actualBrowserPreflightAllowsPersonalVaultModelSelection()throws Exception {
        // 浏览器的真实预检带 Access-Control-Request-*；仅带 Origin 不会触发 Spring 的预检处理。
        mvc.perform(options("/api/models/effective/personal-agent")
                .header("Origin","http://127.0.0.1:5178")
                .header("Access-Control-Request-Method","GET")
                .header("Access-Control-Request-Headers","x-love530-model"))
                .andExpect(status().isOk())
                .andExpect(header().string("Access-Control-Allow-Origin","http://127.0.0.1:5178"))
                .andExpect(header().string("Access-Control-Allow-Headers","x-love530-model"));
        mvc.perform(options("/api/models/selection/personal-agent")
                .header("Origin","http://localhost:5178")
                .header("Access-Control-Request-Method","PUT")
                .header("Access-Control-Request-Headers","content-type,x-love530-model"))
                .andExpect(status().isOk())
                .andExpect(header().string("Access-Control-Allow-Origin","http://localhost:5178"));
    }
    @Test void actualBrowserPreflightRejectsUnknownOriginsAndHeaders()throws Exception {
        mvc.perform(options("/api/models").header("Origin","http://localhost:9998")
                .header("Access-Control-Request-Method","GET").header("Access-Control-Request-Headers","x-love530-model"))
                .andExpect(status().isForbidden());
        mvc.perform(options("/api/models").header("Origin","http://localhost:5178")
                .header("Access-Control-Request-Method","GET").header("Access-Control-Request-Headers","authorization"))
                .andExpect(status().isForbidden());
    }
}
