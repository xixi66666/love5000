package com.example.guitar.config;

import com.example.guitar.auth.web.GuitarAuthInterceptor;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class GuitarWebConfig implements WebMvcConfigurer {

    private final GuitarAuthInterceptor guitarAuthInterceptor;

    public GuitarWebConfig(GuitarAuthInterceptor guitarAuthInterceptor) {
        this.guitarAuthInterceptor = guitarAuthInterceptor;
    }

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(guitarAuthInterceptor)
                .addPathPatterns("/api/**")
                .excludePathPatterns("/api/health");
    }
}
