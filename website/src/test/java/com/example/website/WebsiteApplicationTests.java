package com.example.website;

import com.example.website.auth.WebsiteAuthUserRepository;
import com.example.website.prompt.library.dao.PromptLibraryDao;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;

/**
 * Spring Boot 应用上下文冒烟测试。
 *
 * <p>只验证一件事：{@code website} 的 Bean 装配、自动配置和 Mapper 扫描在没有任何外部依赖时
 * 能完整启动；方法体为空，上下文加载失败本身就是断言失败。</p>
 *
 * <p>隔离手段全部走测试属性，缺一不可：排除 {@code DataSourceAutoConfiguration}
 * 避免连真实 MySQL；关闭 {@code python-a} / {@code quant-a} 的自动启动避免拉起外部 Python 进程；
 * 关闭 {@code website.service-health.scheduled-enabled} 避免后台巡检真实端口。
 * 仅有的两个数据库协作者 {@link PromptLibraryDao} 与
 * {@link com.example.website.auth.WebsiteAuthUserRepository} 用 {@code @MockBean} 替换。</p>
 */
@SpringBootTest(properties = {
        "spring.autoconfigure.exclude=org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration",
        "python-a.auto-start.enabled=false",
        "quant-a.auto-start.enabled=false",
        "website.service-health.scheduled-enabled=false"
})
class WebsiteApplicationTests {

    @MockBean
    private WebsiteAuthUserRepository websiteAuthUserRepository;

    @MockBean
    private PromptLibraryDao promptLibraryDao;

    @Test
    void contextLoads() {
    }

}
