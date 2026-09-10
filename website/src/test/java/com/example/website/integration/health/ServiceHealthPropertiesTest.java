package com.example.website.integration.health;

import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.Collections;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

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
    void rejectsBlankNameAndUnsafeSchemeWithoutLeakingUrl() {
        ServiceHealthProperties blankName = propertiesWith(
                new ServiceHealthDefinition(" ", "http://127.0.0.1/api/health"));
        assertThatThrownBy(blankName::validate)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("service[0] name");

        ServiceHealthProperties unsafeUrl = propertiesWith(
                new ServiceHealthDefinition("private", "file://user:secret@localhost/config"));
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

    private ServiceHealthProperties propertiesWith(ServiceHealthDefinition... definitions) {
        ServiceHealthProperties properties = new ServiceHealthProperties();
        properties.setServices(Arrays.asList(definitions));
        return properties;
    }
}
