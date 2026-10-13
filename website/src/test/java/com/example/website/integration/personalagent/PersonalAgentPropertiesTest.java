package com.example.website.integration.personalagent;

import com.example.website.integration.health.ServiceHealthProperties;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.context.annotation.Configuration;

import static org.assertj.core.api.Assertions.assertThat;

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

    @Configuration
    @EnableConfigurationProperties
    static class PropertiesConfiguration {
    }
}
