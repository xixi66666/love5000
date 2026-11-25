package com.example.common.ai;

import com.fasterxml.jackson.databind.*;
import java.net.*;
import java.io.*;
import java.nio.file.*;

/** 无自动配置的轻量客户端；模型网关与选择状态路径固定，不读取环境变量。 */
public class ModelRoutingClient {
    static final String HUB = "http://127.0.0.1:8080";
    private final ObjectMapper json;
    private final String hub;
    private final Path state;
    private final ModelHttp http;
    public ModelRoutingClient(ObjectMapper json) {
        this(json,HUB,null,new ModelHttp(json,1500,8*1024*1024));
    }
    ModelRoutingClient(ObjectMapper json,String hub,Path state,ModelHttp http) {
        this.json=json;this.hub=hub.replaceAll("/+$","");this.state=state;this.http=http;
        URI uri=URI.create(this.hub);
        if(!"http".equals(uri.getScheme()) || !"127.0.0.1".equals(uri.getHost()) || uri.getUserInfo()!=null
                || !uri.getPath().isEmpty() || uri.getQuery()!=null || uri.getFragment()!=null)
            throw new IllegalArgumentException("模型网关必须是本机回环 HTTP 地址");
    }
    /** 仅供状态页面查询，生成任务直接调用 tryChat。 */
    public boolean active(String service) throws IOException {
        try { return http.request(hub+"/api/models/effective/"+service,"",null,2000).path("active").asBoolean(); }
        catch(ConnectException e) { requireNative(service);return false; }
    }
    /** 当前生效的模型标识（provider:model）；未启用统一选择或网关不可达时返回空串。 */
    public String effectiveModel(String service) {
        try {
            JsonNode body=http.request(hub+"/api/models/effective/"+service,"",null,2000);
            String model=body.path("modelId").asText("");
            return body.path("active").asBoolean(false)?model:"";
        } catch(IOException unavailable) { return ""; }
    }
    /** null 表示明确使用原配置；超时、HTTP 错误和无效 JSON 不自动换模型。 */
    public JsonNode tryChat(String service,Object payload) throws IOException {
        try { return http.request(hub+"/api/models/complete/"+service,"",json.valueToTree(payload),300000,true); }
        catch(ConnectException e) { requireNative(service);return null; }
    }
    public JsonNode chat(String service,Object payload) throws IOException {
        return http.request(hub+"/api/models/chat/"+service,"",json.valueToTree(payload),300000);
    }
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
    private Path findState(){Path p=Paths.get("").toAbsolutePath();while(p!=null){if(Files.exists(p.resolve(".runtime/model-routing.json")))return p.resolve(".runtime/model-routing.json");p=p.getParent();}return null;}
}
