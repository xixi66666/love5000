package com.example.website.integration.models;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Service;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;
import java.nio.file.*;
import java.io.IOException;
import java.util.*;

@Service
public class ModelRoutingService {
    public static final Set<String> SERVICES=new LinkedHashSet<>(Arrays.asList("global","python-a","scrapling-ui","skill-finder","personal-agent"));
    private final ObjectMapper json;
    private final ModelSources sources;
    private final ModelHttp http;
    private final Path statePath;
    private Map<String,String> selections=new LinkedHashMap<>();
    private Map<String,Entry> entries=new LinkedHashMap<>();
    private long checkedAt;
    private static class Entry {
        String id, model, provider, status; boolean available, startable; ModelSources.Source source;
        Map<String,Object> publicView() { Map<String,Object> r=new LinkedHashMap<>();r.put("id",id);r.put("model",model);r.put("provider",provider);r.put("available",available);r.put("startable",startable);r.put("status",status);r.put("capability","text");return r; }
    }
    @org.springframework.beans.factory.annotation.Autowired
    public ModelRoutingService(ObjectMapper json, Environment env) {
        this(json,new ModelSources(env,json,ModelSources.projectRoot()),new ModelHttp(json),
                Paths.get(env.getProperty("MODEL_ROUTING_STATE",ModelSources.projectRoot().resolve(".runtime/model-routing.json").toString())));
    }
    ModelRoutingService(ObjectMapper json,ModelSources sources,ModelHttp http,Path statePath) {
        this.json=json;this.sources=sources;this.http=http;this.statePath=statePath;
        if(Files.exists(statePath)) try { JsonNode state=json.readTree(statePath.toFile());
            for(String service:SERVICES) if(state.path(service).isTextual()) selections.put(service,state.path(service).asText());
        } catch(IOException e) { throw new IllegalStateException("模型选择文件无法读取，请检查文件后重启"); }
    }
    public synchronized Map<String,Object> catalog(boolean refresh) {
        if(refresh || checkedAt==0 || System.currentTimeMillis()-checkedAt>1800000) discover();
        Map<String,Object> result=new LinkedHashMap<>();result.put("success",true);result.put("checkedAt",checkedAt);
        List<Object> list=new ArrayList<>();for(Entry entry:entries.values()) list.add(entry.publicView());
        result.put("models",list);result.put("selections",new LinkedHashMap<>(selections));
        result.put("services",SERVICES);return result;
    }
    private void discover() {
        Map<String,Entry> found=new LinkedHashMap<>();
        Set<String> visited=new HashSet<>();
        for(ModelSources.Source source:sources.read()) {
            String identity=source.base.replaceAll("/v1$", "")+"\n"+source.key;
            if(!source.key.isEmpty() && !visited.add(identity)) continue;
            Set<String> models=new LinkedHashSet<>(); boolean verified=false;
            boolean configured=!source.key.isEmpty() || "strata".equals(source.id);
            if(configured) try { JsonNode data=http.request(source.base+"/models",source.key,null,6000);
                if(data.path("data").isArray()) { verified=true; for(JsonNode model:data.path("data")) {
                    String id=model.path("id").asText();
                    if(isChatModel(id) && source.acceptsModel(id)) models.add(id);
                }}
            } catch(Exception ignored) { }
            if(!verified) for(String name:source.configured) if(!name.trim().isEmpty()) models.add(name.trim());
            if(models.isEmpty() && "strata".equals(source.id)) models.add("Qwen3.8-Flash-Next");
            if(models.isEmpty() && !configured) models.add("尚未配置文本模型");
            for(String model:models) {
                Entry entry=new Entry();entry.id=source.id+":"+model;entry.model=model;entry.provider=source.label;
                entry.source=source;entry.available=verified;entry.status=verified?"模型目录已验证":configured?"连接失败，待验证":"未配置密钥";
                entry.startable="strata".equals(source.id) && Files.isRegularFile(sources.strataHome().resolve("serve/server.py"));
                if(entry.startable && !verified) entry.status="本机服务未启动，可启动后选择";
                found.put(entry.id,entry);
            }
        }
        entries=found;checkedAt=System.currentTimeMillis();
    }
    static boolean isChatModel(String id) {
        String m=id.toLowerCase(Locale.ROOT);
        return !m.isEmpty() && !m.matches(".*(image|dall-e|whisper|tts|asr|embedding|moderation|sora|audio|realtime|transcri|rerank).*");
    }
    public synchronized Map<String,Object> effective(String service) {
        validateService(service);String override=selections.getOrDefault(service,"");
        String selected=override.isEmpty()?selections.getOrDefault("global",""):override;
        Map<String,Object> result=new LinkedHashMap<>();result.put("success",true);result.put("selection",override);
        result.put("modelId",selected);result.put("active",!selected.isEmpty() && !"native".equals(selected));
        result.put("inherited",!"global".equals(service) && override.isEmpty());return result;
    }
    public synchronized Map<String,Object> select(String service,String modelId) {
        validateService(service);
        if(modelId==null || modelId.length()>300) fail(400,"模型选项无效");
        if(!modelId.isEmpty() && !"native".equals(modelId)) {
            catalog(false);Entry entry=entries.get(modelId);
            if(entry==null || !entry.available) fail(409,"该模型尚不可用，请刷新模型目录后重试");
        }
        Map<String,String> next=new LinkedHashMap<>(selections);
        if(modelId.isEmpty()) next.remove(service); else next.put(service,modelId);
        // 文件原子替换，失败时不能向浏览器谎报切换成功。
        try { Files.createDirectories(statePath.toAbsolutePath().getParent());
            Path temp=Files.createTempFile(statePath.toAbsolutePath().getParent(),"routing-",".tmp");
            try { json.writeValue(temp.toFile(),next);
                try { Files.move(temp,statePath,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING); }
                catch(AtomicMoveNotSupportedException e){ Files.move(temp,statePath,StandardCopyOption.REPLACE_EXISTING); }
            } finally { Files.deleteIfExists(temp); }
        } catch(IOException e) { fail(503,"无法保存模型选择，请检查运行目录权限"); }
        selections=next;return effective(service);
    }
    public JsonNode chat(String service,ObjectNode body) {
        if("global".equals(service)) fail(400,"请提供具体服务标识");
        Entry selected;
        synchronized(this) {
            Map<String,Object> current=effective(service);
            if(!Boolean.TRUE.equals(current.get("active"))) fail(409,"该服务正在使用原配置");
            catalog(false);selected=entries.get(current.get("modelId"));
        }
        if(selected==null || !selected.available) fail(503,"已选模型当前不可用，请刷新模型目录；不会自动切换其他模型");
        if(!body.path("messages").isArray() || body.path("messages").size()==0 || body.path("messages").size()>100) fail(400,"messages 参数无效");
        if(body.toString().length()>200000) fail(413,"文本请求过大");
        for(JsonNode message:body.path("messages")) if(!message.path("content").isTextual()) fail(400,"此入口只处理文本任务，截图请使用原视觉模型");
        ObjectNode payload=body.deepCopy();payload.put("model",selected.model);payload.put("stream",false);
        // 禁止客户端通过兼容接口传入任意工具或回调地址。
        payload.remove(Arrays.asList("tools","tool_choice","functions","function_call","webhook","callback_url"));
        if ("mimo".equals(selected.source.id)) {
            // MiMo 官方使用 max_completion_tokens，现有微服务仍可沿用 max_tokens。
            JsonNode maxTokens = payload.remove("max_tokens");
            if (!payload.has("max_completion_tokens")) {
                payload.set("max_completion_tokens", maxTokens == null ? json.getNodeFactory().numberNode(8192) : maxTokens);
            }
            // 直接输出任务默认关闭思考，避免选择器/JSON 的短预算只产生推理内容。
            if (!payload.has("thinking")) payload.putObject("thinking").put("type", "disabled");
            if ("enabled".equals(payload.path("thinking").path("type").asText())) {
                payload.remove(Arrays.asList("temperature", "top_p"));
            }
        }
        try { return http.request(selected.source.base+"/chat/completions",selected.source.key,payload,300000); }
        catch(Exception e) { fail(502,"模型请求失败，请检查提供方状态或私有凭据后重试");return null; }
    }
    private void validateService(String s){if(!SERVICES.contains(s))fail(400,"不支持的服务");}
    private static void fail(int code,String message){throw new ResponseStatusException(HttpStatus.valueOf(code),message);}
}
