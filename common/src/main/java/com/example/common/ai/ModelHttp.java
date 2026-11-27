package com.example.common.ai;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.*;
import java.net.*;
import java.util.Collections;
import java.util.Map;

/**
 * 模型调用的 JSON 传输层，供统一模型客户端等调用方复用。
 *
 * <p>统一处理四件事：把请求体序列化成 JSON、按 Bearer 携带密钥、限制响应体大小、
 * 把失败转换成脱敏异常。属于 {@code common/ai} 的基础设施，不含 Spring 装配，
 * 由使用方自行创建。</p>
 *
 * <p>三处非显然的行为：</p>
 *
 * <p>一是禁用重定向，把 3xx 直接当作错误，避免被上游引导到非预期地址；</p>
 *
 * <p>二是密钥为空时不发 {@code Authorization}，改发 {@code X-Love530-Model: 1} 标记，
 * 让本机模型网关据此识别请求来源；</p>
 *
 * <p>三是异常消息只包含状态码或固定文案，绝不拼接上游响应体、请求头或密钥，
 * 防止敏感内容随异常栈进入日志。</p>
 */
public class ModelHttp {
    /** 复用的序列化器；线程安全，可与其他组件共享。 */
    private final ObjectMapper json;
    /** 建立连接的超时毫秒数，避免上游不可达时长时间阻塞调用线程。 */
    private final int connectTimeout;
    /** 响应体字节上限，超出立即中止并报错，防止超大响应把堆打满。 */
    private final int maxBytes;

    /**
     * 使用默认参数构造：连接超时 4000ms，响应上限 8MB。
     *
     * @param json 序列化器，通常复用应用内的同一个实例
     */
    public ModelHttp(ObjectMapper json) { this(json, 4000, 8 * 1024 * 1024); }
    /**
     * 指定连接超时与响应上限构造。
     *
     * @param json 序列化器
     * @param connectTimeout 连接超时毫秒数
     * @param maxBytes 响应体字节上限，超出即抛异常
     */
    public ModelHttp(ObjectMapper json, int connectTimeout, int maxBytes) {
        this.json=json;this.connectTimeout=connectTimeout;this.maxBytes=maxBytes;
    }
    /**
     * 发送 JSON 请求并返回解析后的对象节点，不接受 204 空响应。
     *
     * @param url 绝对地址，必须是 http 或 https
     * @param key 模型密钥；空串表示走本机网关，不携带 Bearer
     * @param body 请求体；为 {@code null} 时按 GET 发送，否则按 POST 输出 JSON
     * @param timeout 读取超时毫秒数
     * @return 上游返回的 JSON 对象
     * @throws java.io.IOException 非 2xx、响应超限、JSON 非法或根节点不是对象时抛出
     */
    public JsonNode request(String url,String key,JsonNode body,int timeout) throws IOException {
        return request(url,key,body,timeout,false);
    }
    /**
     * 发送 JSON 请求，并可选接受 204 空响应。
     *
     * @param url 绝对地址，必须是 http 或 https
     * @param key 模型密钥；空串表示走本机网关
     * @param body 请求体，可为 {@code null}
     * @param timeout 读取超时毫秒数
     * @param allowNative 为 {@code true} 时，204 视为「明确使用服务原配置」并返回 {@code null}
     * @return 解析后的对象节点；仅当允许原生响应且上游返回 204 时为 {@code null}
     * @throws java.io.IOException 非 2xx（含 3xx 重定向）、响应超限或 JSON 非法时抛出
     */
    public JsonNode request(String url,String key,JsonNode body,int timeout,boolean allowNative) throws IOException {
        return request(url, key, body, timeout, allowNative, Collections.emptyMap());
    }
    /**
     * 执行实际的 HTTP 交互，其余重载最终都汇聚到这里。
     *
     * <p>除 {@code Content-Type} 之外，额外请求头由 {@code headers} 原样注入；密钥为空时用
     * {@code X-Love530-Model: 1} 标记本机网关调用。响应体按 8KB 分块读取并累计字节数，
     * 一旦超过上限立即中止，不等上游把数据发完。</p>
     *
     * @param url 绝对地址
     * @param key 模型密钥；空串表示走本机网关
     * @param body 请求体；为 {@code null} 时使用默认 GET，否则用 POST 输出 JSON
     * @param timeout 读取超时毫秒数
     * @param allowNative 是否把 204 当作有效结果
     * @param headers 额外请求头，允许为空 Map
     * @return 解析后的对象节点；204 且允许原生响应时为 {@code null}
     * @throws java.io.IOException 网络失败、非 2xx、响应超限、JSON 非法或根节点不是对象时抛出
     */
    protected JsonNode request(String url, String key, JsonNode body, int timeout, boolean allowNative,
                               Map<String, String> headers) throws IOException {
        HttpURLConnection connection=(HttpURLConnection)URI.create(url).toURL().openConnection();
        connection.setInstanceFollowRedirects(false);
        connection.setConnectTimeout(connectTimeout);connection.setReadTimeout(timeout);
        headers.forEach(connection::setRequestProperty);
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
