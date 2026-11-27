package com.example.website;

import com.example.common.auth.config.AuthAutoConfiguration;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Import;

/**
 * {@code website} 模块的 Spring Boot 启动类，默认监听 8080 端口（端口、MySQL 数据源、
 * 静态资源路径与子服务集成配置都在 {@code src/main/resources/application.yml}）。
 *
 * <p>组件扫描范围是 {@code com.example.website}，提示词库（{@code prompt.library}）、
 * 旧版提示词控制台（{@code prompt}）、认证适配（{@code auth}）、统一模型入口与
 * 各子服务集成（{@code integration}）都挂在这个包下；Web 示例代码集中在 {@code demos}，
 * 不参与生产链路。</p>
 *
 * <p>{@code @Import(AuthAutoConfiguration.class)} 显式引入 {@code common} 模块的鉴权自动配置，
 * 使 {@code /api/auth} 的注册、登录、登出和 {@code /api/auth/me} 在本模块生效；
 * 用户数据经 {@code com.example.website.auth.WebsiteAuthUserRepository} 落到 {@code xixi} 库的
 * {@code auth_user} 表。{@code python-a}/{@code quant-a} 的自动拉起由
 * {@code ApplicationRunner} 完成，不经过本类。</p>
 */
@SpringBootApplication
@Import(AuthAutoConfiguration.class)
public class WebsiteApplication {

    /**
     * 启动 Spring 容器。
     *
     * <p>不做额外定制：端口占用、数据源不可达等启动期失败由 Spring Boot 直接抛出并终止进程，
     * 不会降级为“仅静态资源可用”的半启动状态。</p>
     *
     * @param args 命令行参数，原样交给 {@link SpringApplication#run(Class, String...)}
     */
    public static void main(String[] args) {
        SpringApplication.run(WebsiteApplication.class, args);
    }

}
