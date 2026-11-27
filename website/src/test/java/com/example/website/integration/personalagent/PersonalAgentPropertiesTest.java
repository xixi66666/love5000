package com.example.website.integration.personalagent;

import com.example.website.integration.health.ServiceHealthProperties;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.context.annotation.Configuration;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * {@code personal-agent.click-start.*} 的配置绑定测试。
 *
 * <p>用 {@link ApplicationContextRunner} 只装配属性类、进程管理器与控制器，不加载完整
 * Spring Boot 上下文，也不启动外部进程。</p>
 *
 * <p>固定两件事：默认值与 {@code application.yml} 一致（5178、{@code /api/health}、
 * 控制台日志），以及 {@code enabled=false} 时管理器与控制器都不注册——关闭点击启动后，
 * 首页不应再存在能拉起个人资料库的入口。</p>
 */
class PersonalAgentPropertiesTest {

    private final ApplicationContextRunner context = new ApplicationContextRunner()
            .withUserConfiguration(PropertiesConfiguration.class, PersonalAgentProperties.class,
                    PersonalAgentProcessManager.class, PersonalAgentController.class)
            .withBean(ObjectMapper.class, ObjectMapper::new)
            .withBean(ServiceHealthProperties.class, ServiceHealthProperties::new);

    @Test
    void bindsClickStartConfigurationAndCreatesNoExternalProcess() {
        context.withPropertyValues("personal-agent.click-start.enabled=true",
                "personal-agent.click-start.work-dir=personal-agent",
                "personal-agent.click-start.command=java",
                "personal-agent.click-start.startup-timeout-seconds=30")
                .run(application -> {
                    assertThat(application).hasSingleBean(PersonalAgentProcessManager.class)
                            .hasSingleBean(PersonalAgentController.class);
                    PersonalAgentProperties properties = application.getBean(PersonalAgentProperties.class);
                    assertThat(properties.getWorkDir()).isEqualTo("personal-agent");
                    assertThat(properties.getCommand()).isEqualTo("java");
                    assertThat(properties.getPort()).isEqualTo(5178);
                    assertThat(properties.getHealthPath()).isEqualTo("/api/health");
                    assertThat(properties.getStartupTimeoutSeconds()).isEqualTo(30);
                    assertThat(properties.isLogToConsole()).isTrue();
                });
    }

    @Test
    void disabledClickStartDoesNotRegisterControllerOrProcessManager() {
        context.withPropertyValues("personal-agent.click-start.enabled=false").run(application -> {
            assertThat(application).doesNotHaveBean(PersonalAgentProcessManager.class)
                    .doesNotHaveBean(PersonalAgentController.class);
            assertThat(application.getBean(PersonalAgentProperties.class).isEnabled()).isFalse();
        });
    }

    /** 只启用 {@code @ConfigurationProperties} 绑定的空配置类，模拟真实自动装配的最小切面。 */
    @Configuration
    @EnableConfigurationProperties
    static class PropertiesConfiguration {
    }
}
