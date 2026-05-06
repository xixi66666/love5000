package com.example.common.auth.config;

import com.example.common.auth.controller.AuthController;
import com.example.common.auth.controller.AuthExceptionHandler;
import com.example.common.auth.repository.AuthUserRepository;
import com.example.common.auth.service.AuthPasswordService;
import com.example.common.auth.service.AuthService;
import com.example.common.auth.service.AuthServiceImpl;
import com.example.common.auth.web.AuthInterceptor;
import org.springframework.boot.autoconfigure.condition.ConditionalOnBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.HandlerInterceptor;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import javax.servlet.http.HttpServletRequest;

@Configuration
@ConditionalOnClass({HttpServletRequest.class, HandlerInterceptor.class})
@ConditionalOnProperty(prefix = "love530.auth", name = "enabled", havingValue = "true", matchIfMissing = true)
@EnableConfigurationProperties(AuthProperties.class)
public class AuthAutoConfiguration {

    @Bean
    @ConditionalOnMissingBean
    public AuthPasswordService authPasswordService() {
        return new AuthPasswordService();
    }

    @Bean
    @ConditionalOnBean(AuthUserRepository.class)
    @ConditionalOnMissingBean
    public AuthService authService(AuthUserRepository authUserRepository,
                                   AuthPasswordService authPasswordService,
                                   AuthProperties authProperties) {
        return new AuthServiceImpl(authUserRepository, authPasswordService, authProperties);
    }

    @Bean
    @ConditionalOnBean(AuthService.class)
    @ConditionalOnMissingBean
    public AuthController authController(AuthService authService) {
        return new AuthController(authService);
    }

    @Bean
    @ConditionalOnMissingBean
    public AuthExceptionHandler authExceptionHandler() {
        return new AuthExceptionHandler();
    }

    @Bean
    @ConditionalOnBean(AuthService.class)
    @ConditionalOnMissingBean
    public AuthInterceptor authInterceptor(AuthService authService) {
        return new AuthInterceptor(authService);
    }

    @Bean
    @ConditionalOnBean(AuthInterceptor.class)
    @ConditionalOnMissingBean(name = "authWebMvcConfigurer")
    public WebMvcConfigurer authWebMvcConfigurer(AuthInterceptor authInterceptor) {
        return new WebMvcConfigurer() {
            @Override
            public void addInterceptors(InterceptorRegistry registry) {
                registry.addInterceptor(authInterceptor).addPathPatterns("/**");
            }
        };
    }

}
