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

/**
 * {@code ModelRoutingClient} 的路由决策测试。
 *
 * <p>用 Mockito 替换 {@code ModelHttp}，既不真的请求模型网关，也能精确校验 URL、空密钥、
 * 超时与「允许原生响应」标志。覆盖一次请求决定路由、204 视为使用原配置、连接被拒时
 * 结合状态文件判定、超时与 HTTP 错误不回退、状态文件损坏，以及非回环网关地址被拒绝。</p>
 */
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
    @Test void effectiveModelOnlyReturnsActiveSelection()throws Exception {
        when(http.request(eq("http://127.0.0.1:8080/api/models/effective/personal-agent"),eq(""),any(),eq(2000)))
                .thenReturn(json.readTree("{\"success\":true,\"active\":true,\"modelId\":\"deepseek:deepseek-flash\"}"));
        assertThat(client.effectiveModel("personal-agent")).isEqualTo("deepseek:deepseek-flash");
        when(http.request(anyString(),eq(""),any(),eq(2000)))
                .thenReturn(json.readTree("{\"success\":true,\"active\":false,\"modelId\":\"\"}"));
        assertThat(client.effectiveModel("personal-agent")).isEmpty();
        when(http.request(anyString(),eq(""),any(),eq(2000))).thenThrow(new SocketTimeoutException());
        assertThat(client.effectiveModel("personal-agent")).isEmpty();
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
