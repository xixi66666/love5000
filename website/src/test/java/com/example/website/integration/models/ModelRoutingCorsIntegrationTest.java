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

/**
 * {@code /api/models/**} 跨域预检在真实 MVC 配置下的集成测试。
 *
 * <p>与只测控制器手写 OPTIONS 的用例不同，本类用
 * {@link AnnotationConfigWebApplicationContext} 加 {@code @EnableWebMvc} 装配真实的
 * HandlerMapping 与预检适配器：浏览器预检在进入控制器方法之前就由 MVC 处理，只测控制器会漏掉
 * 真实的来源与允许头判定。</p>
 *
 * <p>覆盖 personal-agent（5178）在同源页面选择模型所需的预检：GET 与 PUT 放行、允许
 * {@code x-love530-model}；未知来源（9998）和非白名单请求头（authorization）被拒绝。
 * 服务与进程管理都是 mock，不访问真实模型网关。</p>
 */
class ModelRoutingCorsIntegrationTest {
    AnnotationConfigWebApplicationContext context;
    MockMvc mvc;
    /** 最小 MVC 上下文：只注册控制器与两个 mock 协作者，避免拉起真实模型服务或本机进程管理。 */
    @Configuration
    @EnableWebMvc
    static class Config {
        @Bean ModelRoutingService modelRoutingService(){return mock(ModelRoutingService.class);}
        @Bean LocalServicesManager localServicesManager(){return mock(LocalServicesManager.class);}
        @Bean ModelRoutingController modelRoutingController(ModelRoutingService service,LocalServicesManager local){return new ModelRoutingController(service,local);}
    }
    @BeforeEach void setup(){
        // 交给 webAppContextSetup 后，请求才会经过 DispatcherServlet 与真实的 CORS 预检适配器，
        // 而不是控制器里的手写响应头。
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
