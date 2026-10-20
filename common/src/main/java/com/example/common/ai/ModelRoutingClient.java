package com.example.common.ai;

import com.fasterxml.jackson.databind.*;
import java.net.*;
import java.io.*;
import java.nio.file.*;

/** 无自动配置的轻量客户端，独立启动服务时保留原有模型配置。 */
public class ModelRoutingClient {
    private final ObjectMapper json;
    private final String hub;
    public ModelRoutingClient(ObjectMapper json) {
        this.json=json;this.hub=System.getenv().getOrDefault("MODEL_HUB_URL","http://127.0.0.1:8080").replaceAll("/+$","");
        URI uri=URI.create(hub);
        if(!"http".equals(uri.getScheme()) || !"127.0.0.1".equals(uri.getHost()) || uri.getUserInfo()!=null || !uri.getPath().isEmpty()) throw new IllegalArgumentException("MODEL_HUB_URL 必须是本机回环 HTTP 地址");
    }
    public boolean active(String service) throws IOException {
        try { return request("/api/models/effective/"+service,null,2000).path("active").asBoolean(); }
        catch(IOException error) {
            // 已经做过全局选择时网关离线不能悄悄恢复原模型。
            String configured=System.getenv("MODEL_ROUTING_STATE");
            Path state=configured==null?findState():Paths.get(configured);
            if(state!=null && Files.exists(state)) {
                JsonNode selected=json.readTree(state.toFile());String local=selected.path(service).asText();
                String effective=local.isEmpty()?selected.path("global").asText():local;
                if(!effective.isEmpty() && !"native".equals(effective)) throw new IOException("统一模型入口离线，请先启动 website",error);
            }
            return false;
        }
    }
    private Path findState(){Path p=Paths.get("").toAbsolutePath();while(p!=null){if(Files.exists(p.resolve(".runtime/model-routing.json")))return p.resolve(".runtime/model-routing.json");p=p.getParent();}return null;}
    public JsonNode chat(String service,Object payload) throws IOException { return request("/api/models/chat/"+service,json.valueToTree(payload),300000); }
    private JsonNode request(String path,JsonNode body,int timeout)throws IOException {
        HttpURLConnection c=(HttpURLConnection)URI.create(hub+path).toURL().openConnection();
        c.setInstanceFollowRedirects(false);c.setConnectTimeout(1500);c.setReadTimeout(timeout);
        c.setRequestProperty("X-Love530-Model","1");c.setRequestProperty("Content-Type","application/json");
        try {
            if(body!=null){c.setRequestMethod("POST");c.setDoOutput(true);try(OutputStream out=c.getOutputStream()){json.writeValue(out,body);}}
            if(c.getResponseCode()!=200)throw new IOException("统一模型入口请求失败，请检查模型配置");
            try(InputStream in=c.getInputStream()){return json.readTree(in);}
        }finally{c.disconnect();}
    }
}
