package com.example.common.ai;

import com.fasterxml.jackson.databind.*;
import java.net.*;
import java.io.*;
import java.nio.file.*;

/**
 * 统一模型网关的轻量 HTTP 客户端。
 *
 * <p>不做 Spring 自动配置，由使用方自行创建：文本生成调用 {@link #tryChat}，状态页展示调用
 * {@link #active} 与 {@link #effectiveModel}。网关地址固定为 {@code http://127.0.0.1:8080}，
 * 选择状态固定为根目录下 {@code .runtime/model-routing.json}，两者都不读取环境变量。</p>
 *
 * <p>路由原则是「一次请求决定」：{@link #tryChat} 只发一次请求，网关返回 200 就采用统一模型，
 * 返回 204 就使用服务原配置；只有连接被拒、且状态文件确认没有任何统一选择时，才允许离线
 * 使用原配置。超时、HTTP 错误和无效 JSON 一律直接抛出，绝不静默切换模型。</p>
 */
public class ModelRoutingClient {
    /** 固定的模型网关地址；构造时还会校验它必须是无用户信息、无路径、无查询参数的回环 HTTP 地址。 */
    static final String HUB = "http://127.0.0.1:8080";
    /** 序列化器，用于请求体序列化与状态文件解析。 */
    private final ObjectMapper json;
    /** 去掉结尾斜杠后的实际网关地址。 */
    private final String hub;
    /** 统一模型选择状态文件；为 {@code null} 时按当前目录向上查找默认位置。 */
    private final Path state;
    /** 底层 JSON 传输实现，负责超时、大小限制与脱敏错误。 */
    private final ModelHttp http;
    /**
     * 使用默认网关与默认传输参数（连接超时 1500ms、响应上限 8MB）构造。
     *
     * @param json 序列化器，用于请求体序列化与状态文件解析
     */
    public ModelRoutingClient(ObjectMapper json) {
        this(json,HUB,null,new ModelHttp(json,1500,8*1024*1024));
    }
    /**
     * 供测试注入网关地址、状态文件路径与传输实现。
     *
     * @param json 序列化器
     * @param hub 网关基地址，必须是本机回环 HTTP 地址
     * @param state 统一模型选择状态文件，{@code null} 表示自动查找
     * @param http 底层传输实现
     * @throws IllegalArgumentException 网关不是回环 HTTP 地址，或带用户信息、路径、查询参数时抛出
     */
    ModelRoutingClient(ObjectMapper json,String hub,Path state,ModelHttp http) {
        this.json=json;this.hub=hub.replaceAll("/+$","");this.state=state;this.http=http;
        URI uri=URI.create(this.hub);
        if(!"http".equals(uri.getScheme()) || !"127.0.0.1".equals(uri.getHost()) || uri.getUserInfo()!=null
                || !uri.getPath().isEmpty() || uri.getQuery()!=null || uri.getFragment()!=null)
            throw new IllegalArgumentException("模型网关必须是本机回环 HTTP 地址");
    }
    /**
     * 查询服务当前是否走统一模型，仅供状态页展示，不参与生成路由。
     *
     * <p>网关连接被拒时不会直接返回失败，而是走一次 {@link #requireNative} 判定：
     * 若确实没有统一选择则返回 {@code false} 表示可用原配置，否则抛出离线提示。</p>
     *
     * @param service 服务标识
     * @return 网关返回 {@code active} 为真时为 {@code true}
     * @throws IOException 网关返回错误、响应非法或存在统一选择却离线时抛出
     */
    public boolean active(String service) throws IOException {
        try { return http.request(hub+"/api/models/effective/"+service,"",null,2000).path("active").asBoolean(); }
        catch(ConnectException e) { requireNative(service);return false; }
    }
    /**
     * 读取当前生效的模型标识（provider:model）。
     *
     * <p>未启用统一选择、网关不可达或响应中 {@code active} 为 false 时返回空串，
     * 调用方据此显示「跟随服务原配置」。本方法只读状态，不参与生成路由。</p>
     *
     * @param service 服务标识
     * @return 形如 {@code provider:model} 的标识；没有有效选择时为空串
     */
    public String effectiveModel(String service) {
        try {
            JsonNode body=http.request(hub+"/api/models/effective/"+service,"",null,2000);
            String model=body.path("modelId").asText("");
            return body.path("active").asBoolean(false)?model:"";
        } catch(IOException unavailable) { return ""; }
    }
    /**
     * 通过统一网关发起一次生成请求。
     *
     * <p>返回 {@code null} 表示网关明确要求使用服务原配置（HTTP 204），调用方应走自己的模型；
     * 连接被拒时会读取本地状态文件二次确认：确实没有任何统一选择才允许离线用原配置，
     * 否则抛出「统一模型入口离线」的提示。</p>
     *
     * <p>超时、HTTP 错误和无效 JSON 一律原样抛出，不降级为原配置，避免在用户不知情时换模型；
     * 状态文件内容损坏时同样抛出，防止静默使用错误配置。</p>
     *
     * @param service 服务标识，决定状态文件中的覆盖项
     * @param payload 请求体，将被序列化为 JSON
     * @return 网关返回的 JSON；需要原配置时为 {@code null}
     * @throws IOException 网关不可达、状态文件损坏或响应非法时抛出
     */
    public JsonNode tryChat(String service,Object payload) throws IOException {
        try { return http.request(hub+"/api/models/complete/"+service,"",json.valueToTree(payload),300000,true); }
        catch(ConnectException e) { requireNative(service);return null; }
    }
    /**
     * 旧版直连接口，仅保留兼容；新代码应使用 {@link #tryChat}，把是否使用统一模型的决定权交给网关。
     *
     * @param service 服务标识
     * @param payload 请求体
     * @return 网关返回的 JSON，不接受空响应
     * @throws IOException 网关不可达或响应非法时抛出
     */
    public JsonNode chat(String service,Object payload) throws IOException {
        return http.request(hub+"/api/models/chat/"+service,"",json.valueToTree(payload),300000);
    }
    /**
     * 网关连接被拒时判定是否可以离线使用原配置。
     *
     * <p>判定依据是本地状态文件：服务级选择优先于 {@code global}，值为 {@code native} 或为空
     * 表示没有统一选择，允许使用原配置；一旦存在真实模型选择，就说明用户期望走统一入口，
     * 此时必须报错而不是悄悄换模型。</p>
     *
     * <p>状态文件不存在视为「未启用统一选择」；文件存在但内容不是对象、或选择值不是字符串时
     * 视为无法判定，同样抛出异常，避免用坏配置继续生成。</p>
     *
     * @param service 服务标识
     * @throws IOException 状态文件不可读、内容非法，或存在统一选择却离线时抛出
     */
    private void requireNative(String service) throws IOException {
        Path path=state==null?findState():state;
        if(path==null || !Files.exists(path)) return;
        JsonNode selected;
        try { selected=json.readTree(path.toFile()); }
        catch(IOException e) { throw new IOException("无法读取统一模型选择"); }
        if(selected==null || !selected.isObject()) throw new IOException("无法读取统一模型选择");
        if((selected.has(service) && !selected.path(service).isTextual())
                || (selected.has("global") && !selected.path("global").isTextual()))
            throw new IOException("无法读取统一模型选择");
        String local=selected.path(service).asText();
        String effective=local.isEmpty()?selected.path("global").asText():local;
        if(!effective.isEmpty() && !"native".equals(effective)) throw new IOException("统一模型入口离线，请先启动 website");
    }
    /**
     * 从当前工作目录逐级向上查找统一模型选择状态文件。
     *
     * @return 状态文件路径；一路到根都没有时返回 {@code null}
     */
    private Path findState(){Path p=Paths.get("").toAbsolutePath();while(p!=null){if(Files.exists(p.resolve(".runtime/model-routing.json")))return p.resolve(".runtime/model-routing.json");p=p.getParent();}return null;}
}
