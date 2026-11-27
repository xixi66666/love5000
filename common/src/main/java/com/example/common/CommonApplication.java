package com.example.common;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * {@code common} 模块的 Spring Boot 启动入口。
 *
 * <p>本模块定位为被其他业务模块依赖的公共能力库，本身不对外提供服务：打包时
 * {@code spring-boot-maven-plugin} 已跳过可执行 Jar，因此这个类只用于本地验证
 * 上下文能否装配成功。真正对外生效的自动配置入口是
 * {@code META-INF/spring.factories} 中注册的 OssAutoConfiguration 与
 * AuthAutoConfiguration。</p>
 *
 * <p>使用方引入本模块即可，不需要额外扫描 {@code com.example.common} 包。</p>
 */
@SpringBootApplication
public class CommonApplication {

    /**
     * 启动 Spring 上下文，用于人工确认自动配置在无数据库配置的环境下也能完成装配。
     *
     * @param args 原样透传给 {@link SpringApplication#run} 的命令行参数，本模块不解析
     */
    public static void main(String[] args) {
        SpringApplication.run(CommonApplication.class, args);
    }

}
