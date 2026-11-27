package com.example.personalagent;


import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration;
import org.springframework.boot.autoconfigure.SpringBootApplication;


/**
 * personal-agent 模块的 Spring Boot 启动入口（端口 5178）。
 *
 * <p>属应用装配层：只负责引导上下文，不含业务逻辑。排除
 * {@link DataSourceAutoConfiguration} 是有意为之——本服务没有数据库，个人资料全部以
 * Vault 中的 Markdown 文件为准，避免引入数据源后因缺少连接串而启动失败。</p>
 *
 * <p>只由 website 的 03 Deep Woods「个人资料库」卡片点击启动已构建的 jar，
 * 不随 website 启停，也不读取任何数据库配置。</p>
 */
@SpringBootApplication(exclude = DataSourceAutoConfiguration.class)


public class PersonalAgentApplication {
    /** 启动 Spring 容器；不注册命令行参数处理，端口与 Vault 路径都走外部配置。 */
    public static void main(String[] args) { SpringApplication.run(PersonalAgentApplication.class, args); }
}
