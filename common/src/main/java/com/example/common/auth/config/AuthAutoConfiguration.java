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

/**
 * 通用认证能力的自动装配入口。
 *
 * <p>生效条件：classpath 上存在 Spring MVC（{@code HttpServletRequest}、{@code HandlerInterceptor}），
 * 且 {@code love530.auth.enabled} 没有被显式关闭（{@code matchIfMissing = true}，即默认开启）。
 * 装配链路自底向上串联：</p>
 *
 * <p>{@code AuthPasswordService}（无状态，默认直接提供）→ {@code AuthService}（要求容器中已有
 * {@code AuthUserRepository}）→ {@code AuthController} 与 {@code AuthInterceptor}（要求
 * {@code AuthService} 已装配）→ 注册到全部路径的 {@code WebMvcConfigurer}。</p>
 *
 * <p>因此只引入本模块、没有实现 {@code AuthUserRepository} 时，认证链路整体降级：
 * 不生成 {@code AuthService}、{@code AuthController} 和拦截器，也不会拦截任何请求，
 * 只保留密码服务与异常处理器，避免给无关模块强加数据库依赖。</p>
 *
 * <p>所有 Bean 都带 {@code @ConditionalOnMissingBean}，业务模块可用自定义实现覆盖默认装配。</p>
 */
@Configuration
@ConditionalOnClass({HttpServletRequest.class, HandlerInterceptor.class})
@ConditionalOnProperty(prefix = "love530.auth", name = "enabled", havingValue = "true", matchIfMissing = true)
@EnableConfigurationProperties(AuthProperties.class)
public class AuthAutoConfiguration {

    /**
     * 提供 BCrypt 摘要服务；实现无状态，可被多线程共享。
     *
     * @return 默认的密码摘要服务
     */
    @Bean
    @ConditionalOnMissingBean
    public AuthPasswordService authPasswordService() {
        return new AuthPasswordService();
    }

    /**
     * 装配认证服务；缺少 {@code AuthUserRepository} 时整个方法不生效，且不报错。
     *
     * @param authUserRepository 业务模块提供的用户仓储，是认证能力的必需依赖
     * @param authPasswordService 密码摘要服务
     * @param authProperties 认证配置，提供 Session 属性名与密码长度下限
     * @return 认证服务默认实现
     */
    @Bean
    @ConditionalOnBean(AuthUserRepository.class)
    @ConditionalOnMissingBean
    public AuthService authService(AuthUserRepository authUserRepository,
                                   AuthPasswordService authPasswordService,
                                   AuthProperties authProperties) {
        return new AuthServiceImpl(authUserRepository, authPasswordService, authProperties);
    }

    /**
     * 暴露 {@code /api/auth} 下的注册、登录、登出与当前用户接口。
     *
     * @param authService 已装配的认证服务
     * @return 认证控制器
     */
    @Bean
    @ConditionalOnBean(AuthService.class)
    @ConditionalOnMissingBean
    public AuthController authController(AuthService authService) {
        return new AuthController(authService);
    }

    /**
     * 注册认证异常转换器；不依赖认证服务，所以即使没有配置数据库也会生效，
     * 保证 {@code AuthException} 始终有统一的响应结构。
     *
     * @return 全局异常处理器
     */
    @Bean
    @ConditionalOnMissingBean
    public AuthExceptionHandler authExceptionHandler() {
        return new AuthExceptionHandler();
    }

    /**
     * 注册会话校验拦截器。
     *
     * @param authService 已装配的认证服务，用于解析当前用户
     * @return 基于注解的登录校验拦截器
     */
    @Bean
    @ConditionalOnBean(AuthService.class)
    @ConditionalOnMissingBean
    public AuthInterceptor authInterceptor(AuthService authService) {
        return new AuthInterceptor(authService);
    }

    /**
     * 把认证拦截器挂到全部路径。
     *
     * <p>Bean 名固定为 {@code authWebMvcConfigurer}，业务模块可用同名 Bean 替换注册规则
     * （例如追加排除路径），而无需改动本自动配置。</p>
     *
     * @param authInterceptor 已装配的拦截器
     * @return 只负责拦截器注册的 MVC 配置器
     */
    @Bean
    @ConditionalOnBean(AuthInterceptor.class)
    @ConditionalOnMissingBean(name = "authWebMvcConfigurer")
    public WebMvcConfigurer authWebMvcConfigurer(AuthInterceptor authInterceptor) {
        return new WebMvcConfigurer() {
            /**
             * 注册到全部路径；是否真正校验登录态由目标方法或所在类上的
             * {@code @AuthRequired} 决定，未标注的接口不受影响。
             *
             * @param registry MVC 拦截器注册表
             */
            @Override
            public void addInterceptors(InterceptorRegistry registry) {
                registry.addInterceptor(authInterceptor).addPathPatterns("/**");
            }
        };
    }

}
