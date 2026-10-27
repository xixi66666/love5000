package com.example.common.ai;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.*;
import java.net.*;

/** 模型 JSON 传输公共实现：限制响应大小、禁止重定向、只返回脱敏错误。 */
public class ModelHttp {
    private final ObjectMapper json;
    private final int connectTimeout;
    private final int maxBytes;

    public ModelHttp(ObjectMapper json) { this(json, 4000, 8 * 1024 * 1024); }
    public ModelHttp(ObjectMapper json, int connectTimeout, int maxBytes) {
        this.json=json;this.connectTimeout=connectTimeout;this.maxBytes=maxBytes;
    }
    public JsonNode request(String url,String key,JsonNode body,int timeout) throws IOException {
        return request(url,key,body,timeout,false);
    }
    public JsonNode request(String url,String key,JsonNode body,int timeout,boolean allowNative) throws IOException {
        HttpURLConnection connection=(HttpURLConnection)URI.create(url).toURL().openConnection();
        connection.setInstanceFollowRedirects(false);
        connection.setConnectTimeout(connectTimeout);connection.setReadTimeout(timeout);
        connection.setRequestProperty("Content-Type","application/json");
        if(!key.isEmpty()) connection.setRequestProperty("Authorization","Bearer "+key);
        else connection.setRequestProperty("X-Love530-Model","1");
        try {
            if(body!=null) {
                connection.setRequestMethod("POST");connection.setDoOutput(true);
                try(OutputStream out=connection.getOutputStream()) { json.writeValue(out,body); }
            }
            int status=connection.getResponseCode();
            if(status==204 && allowNative) return null;
            if(status<200 || status>=300) throw new IOException("模型服务返回 HTTP "+status);
            try(InputStream in=connection.getInputStream();ByteArrayOutputStream out=new ByteArrayOutputStream()) {
                byte[] buffer=new byte[8192];int count;
                while((count=in.read(buffer))!=-1) {
                    if(out.size()+count>maxBytes) throw new IOException("模型响应过大");
                    out.write(buffer,0,count);
                }
                JsonNode result;
                try { result=json.readTree(out.toByteArray()); }
                catch(IOException e) { throw new IOException("模型返回了无效 JSON"); }
                if(result==null || !result.isObject()) throw new IOException("模型响应格式无效");
                return result;
            }
        } finally { connection.disconnect(); }
    }
}
