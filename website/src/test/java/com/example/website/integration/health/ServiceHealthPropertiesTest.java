package com.example.website.integration.health;

import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.Collections;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * 健康巡检配置 {@link ServiceHealthProperties} 的默认值与校验规则测试。
 *
 * <p>锁定文档中承诺的默认值：连接超时 2000ms、读取超时 3000ms、巡检间隔 1800000ms（30 分钟）、
 * 后台巡检默认开启，且服务清单保持配置顺序。校验侧要求拒绝：重名服务、非正数的间隔与超时、
 * 空白服务名、非 http(s) 或缺少 host 的 URL。</p>
 *
 * <p>安全约定：URL 非法时异常信息只能带服务名，不能把 {@code file://user:secret@...}
 * 里的凭据写进日志，用例用 {@code hasMessageNotContaining("secret")} 守住这一点。
 * 隔离：纯 POJO 单测，不起 Spring 上下文、不读 application.yml、不联网。</p>
 */
class ServiceHealthPropertiesTest {

    @Test
    void defaultsAndConfiguredOrderAreStable() {
        ServiceHealthProperties properties = new ServiceHealthProperties();
        properties.setServices(Arrays.asList(
                new ServiceHealthDefinition("imagetemplate", "http://127.0.0.1:8082/api/health"),
                new ServiceHealthDefinition("video", "https://video.example/api/health")));

        properties.validate();

        assertThat(properties.getConnectTimeoutMs()).isEqualTo(2000);
        assertThat(properties.getReadTimeoutMs()).isEqualTo(3000);
        assertThat(properties.getCheckIntervalMs()).isEqualTo(1800000L);
        assertThat(properties.isScheduledEnabled()).isTrue();
        assertThat(properties.getServices())
                .extracting(ServiceHealthDefinition::getName)
                .containsExactly("imagetemplate", "video");
    }

    @Test
    void rejectsDuplicateNames() {
        ServiceHealthProperties properties = propertiesWith(
                new ServiceHealthDefinition("imagetemplate", "http://127.0.0.1:8082/api/health"),
                new ServiceHealthDefinition("imagetemplate", "http://127.0.0.1:8089/api/health"));

        assertThatThrownBy(properties::validate)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("duplicate service name: imagetemplate");
    }

    @Test
    void rejectsNonPositiveCheckInterval() {
        ServiceHealthProperties properties = new ServiceHealthProperties();
        properties.setCheckIntervalMs(0);
        assertThatThrownBy(properties::validate).hasMessageContaining("check-interval-ms");
    }

    @Test
    void rejectsBlankNameAndUnsafeSchemeWithoutLeakingUrl() {
        ServiceHealthProperties blankName = propertiesWith(
                new ServiceHealthDefinition(" ", "http://127.0.0.1/api/health"));
        assertThatThrownBy(blankName::validate)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("service[0] name");

        ServiceHealthProperties unsafeUrl = propertiesWith(
                new ServiceHealthDefinition("private", "file://user:secret@localhost/config"));
        // 报错只带服务名：URL 里可能有凭据，不能进日志。
        assertThatThrownBy(unsafeUrl::validate)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("private")
                .hasMessageNotContaining("secret");
    }

    @Test
    void rejectsNonPositiveTimeouts() {
        ServiceHealthProperties properties = new ServiceHealthProperties();
        properties.setServices(Collections.singletonList(
                new ServiceHealthDefinition("imagetemplate", "http://127.0.0.1:8082/api/health")));
        properties.setConnectTimeoutMs(0);

        assertThatThrownBy(properties::validate)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("connect-timeout-ms");
    }

    @Test
    void rejectsHttpUrlsWithoutAHost() {
        ServiceHealthProperties properties = propertiesWith(
                new ServiceHealthDefinition("broken", "http:/api/health"));

        assertThatThrownBy(properties::validate)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("broken")
                .hasMessageContaining("invalid health URL");
    }

    /** 用给定清单构造配置，供各条非法输入用例复用。 */
    private ServiceHealthProperties propertiesWith(ServiceHealthDefinition... definitions) {
        ServiceHealthProperties properties = new ServiceHealthProperties();
        properties.setServices(Arrays.asList(definitions));
        return properties;
    }
}
