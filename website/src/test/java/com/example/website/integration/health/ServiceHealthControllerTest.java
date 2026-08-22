package com.example.website.integration.health;

import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.util.Arrays;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class ServiceHealthControllerTest {

    @Test
    void returnsAggregateHealthDetailsWithHttpTwoHundred() throws Exception {
        ServiceHealthDefinition guitar = new ServiceHealthDefinition(
                "guitar", "http://127.0.0.1:8088/api/health");
        ServiceHealthDefinition video = new ServiceHealthDefinition(
                "video", "http://127.0.0.1:5176/api/health");
        ServiceHealthSummary summary = new ServiceHealthSummary(
                true,
                false,
                Arrays.asList(
                        ServiceHealthResult.healthy(guitar, 200, 12),
                        ServiceHealthResult.unhealthy(video, null, 7, "Connection failed")));
        ServiceHealthAggregator aggregator = mock(ServiceHealthAggregator.class);
        when(aggregator.checkAll()).thenReturn(summary);
        MockMvc mockMvc = MockMvcBuilders
                .standaloneSetup(new ServiceHealthController(aggregator))
                .build();

        mockMvc.perform(get("/api/services/health"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.healthy").value(false))
                .andExpect(jsonPath("$.services[0].name").value("guitar"))
                .andExpect(jsonPath("$.services[0].statusCode").value(200))
                .andExpect(jsonPath("$.services[0].message").isEmpty())
                .andExpect(jsonPath("$.services[1].name").value("video"))
                .andExpect(jsonPath("$.services[1].statusCode").isEmpty())
                .andExpect(jsonPath("$.services[1].message").value("Connection failed"));
    }
}
