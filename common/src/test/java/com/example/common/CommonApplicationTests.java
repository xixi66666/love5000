package com.example.common;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;

/**
 * 上下文冒烟测试：确认 {@code common} 的自动配置能在没有数据库的 Spring 环境里完成装配。
 *
 * <p>用例排除了 {@code DataSourceAutoConfiguration}，避免本地没有 MySQL 时失败；
 * 不启动外部进程、不连接 OSS，只断言上下文能够加载。</p>
 */
@SpringBootTest(properties = "spring.autoconfigure.exclude=org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration")
class CommonApplicationTests {

    @Test
    void contextLoads() {
    }

}
