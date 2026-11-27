package com.example.common.ai;

import com.fasterxml.jackson.databind.*;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicInteger;
import static org.assertj.core.api.Assertions.*;

/**
 * {@code ModelHttp} 的传输行为测试。
 *
 * <p>用 JDK 自带的 {@code HttpServer} 在本机随机端口起一个可编程端点，不连接外部网络；
 * 覆盖正常 JSON 往返、Bearer 与网关标记二选一、204 空响应、非 2xx 错误脱敏、
 * 禁止跟随重定向，以及响应超限与非法 JSON 被拒绝。断言重点之一是错误消息不得泄露
 * 上游响应体或密钥。</p>
 */
class ModelHttpTest {
    HttpServer server;
    ObjectMapper json=new ObjectMapper();
    String url;
    int status;
    String body;
    String authorization;
    String marker;
    JsonNode payload;
    AtomicInteger redirected=new AtomicInteger();

    @BeforeEach void setup()throws Exception {
        status=200;body="{\"model\":\"native\"}";
        server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
        server.createContext("/chat",exchange->{
            authorization=exchange.getRequestHeaders().getFirst("Authorization");
            marker=exchange.getRequestHeaders().getFirst("X-Love530-Model");
            payload=json.readTree(exchange.getRequestBody());
            byte[] bytes=body.getBytes(StandardCharsets.UTF_8);
            if(status==302) exchange.getResponseHeaders().set("Location","/redirected");
            exchange.sendResponseHeaders(status,status==204?-1:bytes.length);
            if(status!=204)try(OutputStream out=exchange.getResponseBody()){out.write(bytes);}
            exchange.close();
        });
        server.createContext("/redirected",exchange->{redirected.incrementAndGet();exchange.sendResponseHeaders(204,-1);exchange.close();});
        server.start();url="http://127.0.0.1:"+server.getAddress().getPort()+"/chat";
    }
    @AfterEach void close(){server.stop(0);}
    @Test void sharedTransportSendsJsonAndBearerOrGatewayMarker()throws Exception {
        ModelHttp http=new ModelHttp(json);
        assertThat(http.request(url,"test-key",json.readTree("{\"model\":\"native\"}"),1000).path("model").asText()).isEqualTo("native");
        assertThat(authorization).isEqualTo("Bearer test-key");assertThat(payload.path("model").asText()).isEqualTo("native");
        status=204;
        assertThat(http.request(url,"",json.createObjectNode(),1000,true)).isNull();
        assertThat(authorization).isNull();assertThat(marker).isEqualTo("1");
        assertThatThrownBy(()->http.request(url,"",json.createObjectNode(),1000)).isInstanceOf(IOException.class);
    }
    @Test void failuresAndRedirectsAreSanitizedAndNeverFollowed() {
        ModelHttp http=new ModelHttp(json);body="private upstream detail";
        status=401;
        assertThatThrownBy(()->http.request(url,"test-key",json.createObjectNode(),1000)).hasMessageContaining("401").hasMessageNotContaining("private").hasMessageNotContaining("test-key");
        status=302;
        assertThatThrownBy(()->http.request(url,"test-key",json.createObjectNode(),1000)).hasMessageContaining("302");
        assertThat(redirected.get()).isZero();
    }
    @Test void invalidOrOversizedJsonIsRejected() {
        ModelHttp http=new ModelHttp(json,1000,32);
        body="null";
        assertThatThrownBy(()->http.request(url,"",json.createObjectNode(),1000)).isInstanceOf(IOException.class);
        body="private malformed response";
        assertThatThrownBy(()->http.request(url,"",json.createObjectNode(),1000)).hasMessageNotContaining("private");
        body="{\"text\":\"abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyz\"}";
        assertThatThrownBy(()->http.request(url,"",json.createObjectNode(),1000)).hasMessageContaining("过大");
    }
}
