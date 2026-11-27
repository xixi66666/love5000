package com.example.imagetemplate;

import org.mybatis.spring.boot.autoconfigure.MybatisAutoConfiguration;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration;

/**
 * 图片提示词模板服务（imagetemplate）的 Spring Boot 启动入口。
 *
 * <p>本模块的数据源是 classpath 下的两份 JSON（精选模板与 Prompt Console 大库），
 * 不访问数据库，也没有 MyBatis Mapper，因此显式排除
 * {@link DataSourceAutoConfiguration} 与 {@link MybatisAutoConfiguration}：父工程带入的
 * JDBC/MyBatis 自动配置在缺少 {@code DataSource} 时会让应用启动失败。</p>
 *
 * <p>启动后默认监听 8082，工作台页面由 {@code classpath:/static/} 提供，
 * 接口挂载在 {@code /api/image-templates} 下。</p>
 */
@SpringBootApplication(exclude = {DataSourceAutoConfiguration.class, MybatisAutoConfiguration.class})
public class ImageTemplateApplication {

    /**
     * 启动 Spring 容器并进入常驻服务。
     *
     * @param args 命令行参数，原样转交给 {@link SpringApplication}
     */
    public static void main(String[] args) {
        SpringApplication.run(ImageTemplateApplication.class, args);
    }
}

