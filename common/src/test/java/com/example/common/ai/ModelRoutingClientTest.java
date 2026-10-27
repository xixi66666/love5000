package com.example.common.ai;

import com.fasterxml.jackson.databind.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import java.io.IOException;
import java.net.*;
import java.nio.file.*;
import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;

class ModelRoutingClientTest {
    @TempDir Path dir;
    ObjectMapper json=new ObjectMapper();
    ModelHttp http;
    ModelRoutingClient client;
    Path state;

    @BeforeEach void setup() {
        http=mock(ModelHttp.class);state=dir.resolve("selection.json");
        client=new ModelRoutingClient(json,"http://127.0.0.1:8080",state,http);
    }
    @Test void generationUsesOneRequestWithoutEffectiveProbeOrProviderCredentials()throws Exception {
        when(http.request(endsWith("/complete/personal-agent"),eq(""),any(),eq(300000),eq(true)))
                .thenReturn(json.readTree("{\"model\":\"selected\"}"));
        assertThat(client.tryChat("personal-agent",json.createObjectNode()).path("model").asText()).isEqualTo("selected");
        verify(http).request(eq("http://127.0.0.1:8080/api/models/complete/personal-agent"),eq(""),any(),eq(300000),eq(true));
        verifyNoMoreInteractions(http);
    }
    @Test void explicitNativeResponseAllowsLocalConfiguration()throws Exception {
        assertThat(client.tryChat("personal-agent",json.createObjectNode())).isNull();
    }
    @Test void refusedConnectionChecksGlobalAndServiceOverride()throws Exception {
        when(http.request(anyString(),anyString(),any(),anyInt(),eq(true))).thenThrow(new ConnectException());
        Files.write(state,"{\"global\":\"mimo:pro\",\"personal-agent\":\"native\"}".getBytes("UTF-8"));
        assertThat(client.tryChat("personal-agent",json.createObjectNode())).isNull();
        assertThatThrownBy(()->client.tryChat("python-a",json.createObjectNode())).hasMessageContaining("离线");
        Files.write(state,"{\"global\":\"native\"}".getBytes("UTF-8"));
        assertThat(client.tryChat("python-a",json.createObjectNode())).isNull();
    }
    @Test void timeoutOrHttpFailureNeverTurnsIntoNativeEvenWithNoSelection()throws Exception {
        when(http.request(anyString(),anyString(),any(),anyInt(),eq(true))).thenThrow(new SocketTimeoutException());
        assertThatThrownBy(()->client.tryChat("personal-agent",json.createObjectNode())).isInstanceOf(SocketTimeoutException.class);
        when(http.request(anyString(),anyString(),any(),anyInt(),eq(true))).thenThrow(new IOException("HTTP 502"));
        assertThatThrownBy(()->client.tryChat("personal-agent",json.createObjectNode())).hasMessageContaining("502");
    }
    @Test void corruptStateDoesNotSilentlyFallBack()throws Exception {
        when(http.request(anyString(),anyString(),any(),anyInt(),eq(true))).thenThrow(new ConnectException());
        for(String invalid:new String[]{"null","[]","{\"global\":[]}","bad"}) {
            Files.write(state,invalid.getBytes("UTF-8"));
            assertThatThrownBy(()->client.tryChat("personal-agent",json.createObjectNode())).hasMessageContaining("无法读取");
        }
    }
    @Test void remoteHubAndUrlCredentialsAreRejected() {
        for(String url:new String[]{"https://example.com","http://user@127.0.0.1:8080","http://127.0.0.1:8080?key=x"})
            assertThatThrownBy(()->new ModelRoutingClient(json,url,state,http)).isInstanceOf(IllegalArgumentException.class);
    }
}
