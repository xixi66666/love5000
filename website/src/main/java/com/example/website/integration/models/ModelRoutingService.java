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
import java.util.concurrent.locks.ReentrantLock;

/**
 * 统一模型网关的核心服务。
 *
 * <p>属于 integration/models 的业务层，负责三件事：模型目录探测、选择持久化、文本生成
 * 代理。目录来源是项目根目录的 {@code model.properties}（由 {@link ModelSources} 读取），
 * 密钥只在探测与生成时使用，既不进目录响应，也不写入状态文件。</p>
 *
 * <p>目录探测：对每个已配置的提供方请求 {@code /models}，超时 6000 毫秒；配置里显式写了
 * 模型清单时以清单为准，留空才展示上游实际返回的聊天模型。结果发布为不可变快照，
 * {@code checkedAt} 起 1800000 毫秒（30 分钟）内直接复用，手动刷新则强制重探。
 * 探测锁只包住网络请求，已有模型查询与生成不会被慢刷新阻塞。</p>
 *
 * <p>选择持久化：状态文件固定在项目根 {@code .runtime/model-routing.json}，只保存服务到
 * 模型 ID 的映射，不含任何凭据。写入走「临时文件加原子替换」，替换失败时直接返回 503，
 * 绝不向浏览器谎报切换成功。</p>
 *
 * <p>生成代理：上游调用超时 300000 毫秒；请求体限制 100 条消息、20 万字符，且只接受文本
 * 内容。客户端传入的 {@code tools}、{@code function_call}、回调地址等字段会被移除，
 * 避免借兼容接口构造任意工具调用。OpenCode Go 位于 Cloudflare 之后，必须复用带自定义
 * 请求头的调用方式，否则会被 1010 拒绝；MiMo 需要把 {@code max_tokens} 改写为
 * {@code max_completion_tokens}，并默认关闭深度思考。</p>
 */
@Service
public class ModelRoutingService {
    /** 支持统一模型路由的服务标识；{@code global} 是其它服务的继承来源，顺序即接口返回顺序。 */
    public static final Set<String> SERVICES=new LinkedHashSet<>(Arrays.asList("global","python-a","scrapling-ui","skill-finder","personal-agent"));
    private final ObjectMapper json;
    private final ModelSources sources;
    private final ModelHttp http;
    /** 选择结果持久化文件：项目根 {@code .runtime/model-routing.json}，只存模型 ID。 */
    private final Path statePath;
    /** 内存选择表，受 {@code this} 监视器保护；写文件成功后才替换，保证响应与磁盘一致。 */
    private Map<String,String> selections=new LinkedHashMap<>();
    /** 目录探测锁，只包裹网络请求，不与选择读写共用，避免慢刷新阻塞生成。 */
    private final ReentrantLock discoveryLock = new ReentrantLock();
    /** 已发布的目录快照；{@code checkedAt} 为 0 表示尚未成功探测过。 */
    private volatile CatalogSnapshot catalog = new CatalogSnapshot(Collections.emptyMap(), 0);
    /**
     * 一次目录探测的不可变结果。
     *
     * <p>整体替换而不是原地修改，读取方不会看到半轮探测的中间状态；
     * 构造时对条目表做不可变包装，避免发布后被意外改写。</p>
     */
    private static class CatalogSnapshot {
        final Map<String,Entry> entries;
        final long checkedAt;
        CatalogSnapshot(Map<String,Entry> entries, long checkedAt) {
            this.entries = Collections.unmodifiableMap(new LinkedHashMap<>(entries));
            this.checkedAt = checkedAt;
        }
    }
    /**
     * 目录中的单个模型条目。
     *
     * <p>对外只暴露 {@link #publicView()} 的字段，{@code source} 保留提供方地址与密钥，
     * 仅供生成阶段内部使用，不参与序列化。</p>
     */
    private static class Entry {
        String id, model, provider, status; boolean available, startable; ModelSources.Source source;
        /**
         * 生成可直接返回给浏览器的条目视图。
         *
         * <p>刻意不包含提供方地址与密钥；能力固定为 {@code text}，因为该入口只代理文本模型。</p>
         *
         * @return 含 {@code id}、{@code model}、{@code provider}、{@code available}、
         *         {@code startable}、{@code status} 与 {@code capability} 的字段表
         */
        Map<String,Object> publicView() { Map<String,Object> r=new LinkedHashMap<>();r.put("id",id);r.put("model",model);r.put("provider",provider);r.put("available",available);r.put("startable",startable);r.put("status",status);r.put("capability","text");return r; }
    }
    /**
     * Spring 构造器：从项目根定位配置与状态文件。
     *
     * <p>状态文件固定为 {@code <项目根>/.runtime/model-routing.json}，不接受环境变量覆盖，
     * 避免不同启动方式读写到不同位置导致选择丢失。</p>
     *
     * @param json JSON 序列化器
     * @param env  读取本机服务目录等配置
     */
    @org.springframework.beans.factory.annotation.Autowired
    public ModelRoutingService(ObjectMapper json, Environment env) {
        this(json,new ModelSources(env,ModelSources.projectRoot()),new ModelHttp(json),
                ModelSources.projectRoot().resolve(".runtime/model-routing.json"));
    }
    /**
     * 测试构造器：允许注入目录来源、HTTP 客户端与状态文件路径。
     *
     * <p>构造时读取已有选择；文件存在但无法解析时直接让启动失败，而不是静默丢弃用户的选择。</p>
     *
     * @param json      JSON 序列化器
     * @param sources   模型提供方来源
     * @param http      上游 HTTP 客户端
     * @param statePath 选择状态文件路径
     * @throws IllegalStateException 状态文件存在但无法读取或解析时抛出
     */
    ModelRoutingService(ObjectMapper json,ModelSources sources,ModelHttp http,Path statePath) {
        this.json=json;this.sources=sources;this.http=http;this.statePath=statePath;
        if(Files.exists(statePath)) try { JsonNode state=json.readTree(statePath.toFile());
            for(String service:SERVICES) if(state.path(service).isTextual()) selections.put(service,state.path(service).asText());
        } catch(IOException e) { throw new IllegalStateException("模型选择文件无法读取，请检查文件后重启"); }
    }
    /**
     * 返回模型目录与当前选择，必要时先重新探测。
     *
     * <p>探测条件：强制刷新、从未探测过、或距上次成功探测超过 30 分钟。并发刷新时后来者
     * 只在锁内确认快照是否已被替换，从而复用刚完成的结果，避免对同一批提供方重复发请求。</p>
     *
     * @param refresh {@code true} 表示忽略缓存强制探测
     * @return 含 {@code success}、{@code checkedAt}、{@code models}、{@code selections} 与
     *         {@code services} 的响应表
     */
    public Map<String,Object> catalog(boolean refresh) {
        CatalogSnapshot previous = catalog;
        if(refresh || previous.checkedAt==0 || System.currentTimeMillis()-previous.checkedAt>1800000) {
            discoveryLock.lock();
            try {
                // 并发刷新复用刚完成的探测；网络请求不持有模型选择锁。
                if (catalog == previous) catalog = new CatalogSnapshot(discover(), System.currentTimeMillis());
            } finally { discoveryLock.unlock(); }
        }
        CatalogSnapshot snapshot = catalog;
        Map<String,Object> result=new LinkedHashMap<>();result.put("success",true);result.put("checkedAt",snapshot.checkedAt);
        List<Object> list=new ArrayList<>();for(Entry entry:snapshot.entries.values()) list.add(entry.publicView());
        result.put("models",list);
        synchronized(this) { result.put("selections",new LinkedHashMap<>(selections)); }
        result.put("services",SERVICES);return result;
    }
    /**
     * 逐个提供方探测模型目录，组装去重后的条目表。
     *
     * <p>同一「基址加密钥」组合只探测一次；探测失败不抛异常，只把该提供方的条目标记为未验证。
     * 条目状态按优先级给出固定中文说明：模型目录已验证、未配置密钥、连接失败待验证、
     * 目录未列出该模型，以及 Strata 的「本机服务未启动，可启动后选择」。配置了模型清单时以
     * 清单为准，上游返回的模型只用于判断可用性。</p>
     *
     * @return 以 {@code 提供方:模型} 为键、保持配置顺序的条目表
     */
    private Map<String,Entry> discover() {
        Map<String,Entry> found=new LinkedHashMap<>();
        Set<String> visited=new HashSet<>();
        for(ModelSources.Source source:sources.read()) {
            String identity=source.base.replaceAll("/v1$", "")+"\n"+source.key;
            if(!source.key.isEmpty() && !visited.add(identity)) continue;
            Set<String> models=new LinkedHashSet<>(); Set<String> discovered=new LinkedHashSet<>();
            boolean verified=false;
            boolean configured=!source.key.isEmpty() || "strata".equals(source.id);
            if(configured) try {
                // OpenCode Go 位于 Cloudflare 之后，缺省 Java 客户端标识会被 1010 拒绝，必须复用其请求头。
                JsonNode data="opencode-go".equals(source.id)
                        ?http.requestOpenCodeGo(source.base+"/models",source.key,null,6000)
                        :http.request(source.base+"/models",source.key,null,6000);
                if(data.path("data").isArray()) { verified=true; for(JsonNode model:data.path("data")) {
                    String id=model.path("id").asText();
                    if(isChatModel(id)) discovered.add(id);
                }}
            } catch(Exception ignored) { }
            // model.properties 里的模型目录优先；留空时才展示提供方实际返回的聊天模型。
            if(!source.configured.isEmpty()) models.addAll(source.configured);
            else for(String id:discovered) if(source.acceptsModel(id)) models.add(id);
            if(models.isEmpty() && "strata".equals(source.id)) models.add("Qwen3.8-Flash-Next");
            if(models.isEmpty() && !configured) models.add("尚未配置文本模型");
            for(String model:models) {
                Entry entry=new Entry();entry.id=source.id+":"+model;entry.model=model;entry.provider=source.label;
                entry.source=source;
                entry.available=verified && discovered.contains(model);
                if(entry.available) entry.status="模型目录已验证";
                else if(!configured) entry.status="未配置密钥";
                else if(!verified) entry.status="连接失败，待验证";
                else entry.status="目录未列出该模型";
                entry.startable="strata".equals(source.id) && Files.isRegularFile(sources.strataHome().resolve("serve/server.py"));
                if(entry.startable && !verified) entry.status="本机服务未启动，可启动后选择";
                found.put(entry.id,entry);
            }
        }
        return found;
    }
    /**
     * 判断上游返回的模型标识是否属于文本聊天模型。
     *
     * <p>按关键词排除图片、语音、向量、审核、实时音视频等非文本模型。这是黑名单式过滤，
     * 因此上游返回的模型还会与配置清单交叉验证后才标记为可用。</p>
     *
     * @param id 上游模型标识
     * @return 看起来可用于文本生成时返回 {@code true}
     */
    static boolean isChatModel(String id) {
        String m=id.toLowerCase(Locale.ROOT);
        return !m.isEmpty() && !m.matches(".*(image|dall-e|whisper|tts|asr|embedding|moderation|sora|audio|realtime|transcri|rerank).*");
    }
    /**
     * 计算某个服务当前实际生效的模型。
     *
     * <p>服务自身有显式选择时用显式值，否则继承 {@code global}；清除选择即回到继承。
     * {@code active} 为 false 表示没有启用统一模型（空选择或显式 {@code native}），
     * 各服务应继续使用自己的原配置。</p>
     *
     * @param service 服务标识
     * @return {@code selection}、{@code modelId}、{@code active} 与 {@code inherited}
     * @throws ResponseStatusException 服务标识不受支持时抛出 400
     */
    public synchronized Map<String,Object> effective(String service) {
        validateService(service);String override=selections.getOrDefault(service,"");
        String selected=override.isEmpty()?selections.getOrDefault("global",""):override;
        Map<String,Object> result=new LinkedHashMap<>();result.put("success",true);result.put("selection",override);
        result.put("modelId",selected);result.put("active",!selected.isEmpty() && !"native".equals(selected));
        result.put("inherited",!"global".equals(service) && override.isEmpty());return result;
    }
    /**
     * 保存或清除某个服务的模型选择。
     *
     * <p>非空选择必须先通过目录校验，只有已验证可用的模型才允许持久化。文件先写临时文件再
     * 原子移动，移动成功后才更新内存表；任何一步失败都返回 503 并保持原选择不变，
     * 临时文件在 finally 中清理。</p>
     *
     * @param service 服务标识
     * @param modelId 模型 ID，空串表示清除，{@code native} 表示显式使用服务原配置
     * @return 保存后的生效状态
     * @throws ResponseStatusException 服务或模型非法（400）、模型不可用（409）、
     *                                 保存失败（503）时抛出
     */
    public Map<String,Object> select(String service,String modelId) {
        validateService(service);
        if(modelId==null || modelId.length()>300) fail(400,"模型选项无效");
        if(!modelId.isEmpty() && !"native".equals(modelId)) {
            catalog(false);Entry entry=catalog.entries.get(modelId);
            if(entry==null || !entry.available) fail(409,"该模型尚不可用，请刷新模型目录后重试");
        }
        synchronized(this) {
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
    }
    /**
     * 兼容旧调用方的生成入口，未启用统一模型时报错。
     *
     * @param service 服务标识，不能是 {@code global}
     * @param body    OpenAI 兼容请求体
     * @return 上游响应
     */
    public JsonNode chat(String service,ObjectNode body) {
        return generate(service, body, false);
    }
    /**
     * 一次请求完成路由；null 表示明确使用服务原配置，尚未调用任何上游。
     *
     * <p>这是服务端调用的入口：上层据此区分「没有启用统一模型」与「网关故障」。
     * 未启用统一模型时在此返回 {@code null}，由调用方回退到自己的模型配置；
     * 一旦真正调用上游，超时或 HTTP 错误都会抛出 502，不会被折叠成 {@code null}。</p>
     *
     * @param service 服务标识，不能是 {@code global}
     * @param body    OpenAI 兼容请求体，只接受文本消息
     * @return 上游 chat completions 的原始响应；没有统一选择时返回 {@code null}
     * @throws ResponseStatusException 选择、请求体或上游状态不符合要求时抛出对应状态码
     */
    public JsonNode complete(String service,ObjectNode body) {
        return generate(service, body, true);
    }
    /**
     * 执行一次路由生成：解析选择、校验请求、改写载荷、调用上游。
     *
     * <p>两条入口的共同实现。成功路径只有一条，失败路径全部转换成固定中文提示：未选择统一
     * 模型、模型不可用、消息非法、请求过大、含非文本内容、上游异常。上游异常统一映射为 502，
     * 不自动切换其它模型，避免在用户不知情时把请求发给别的提供方。</p>
     *
     * @param service     服务标识，不能是 {@code global}
     * @param body        OpenAI 兼容请求体
     * @param allowNative 是否允许「没有统一选择」作为正常结果返回 {@code null}
     * @return 上游 chat completions 的原始响应；{@code allowNative} 为真且无选择时为
     *         {@code null}
     * @throws ResponseStatusException 参数、选择或上游状态不符合要求时抛出对应状态码
     */
    private JsonNode generate(String service,ObjectNode body,boolean allowNative) {
        if("global".equals(service)) fail(400,"请提供具体服务标识");
        Map<String,Object> current=effective(service);
        if(!Boolean.TRUE.equals(current.get("active"))) {
            if (allowNative) return null;
            fail(409,"该服务正在使用原配置");
        }
        // 生成复用已发布的目录快照，手动刷新不会阻塞已有模型请求。
        if (catalog.checkedAt == 0) catalog(false);
        Entry selected=catalog.entries.get(current.get("modelId"));
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
        String url = selected.source.base + "/chat/completions";
        try {
            if ("opencode-go".equals(selected.source.id)) {
                return http.requestOpenCodeGoChat(url, selected.source.key, payload, 300000);
            }
            return http.request(url, selected.source.key, payload, 300000);
        }
        catch(Exception e) { fail(502,"模型请求失败，请检查提供方状态或私有凭据后重试");return null; }
    }
    /**
     * 校验服务标识是否在支持列表内。
     *
     * @param s 待校验的服务标识
     * @throws ResponseStatusException 不在列表内时抛出 400
     */
    private void validateService(String s){if(!SERVICES.contains(s))fail(400,"不支持的服务");}
    /**
     * 以指定状态码和中文原因中断请求。
     *
     * @param code    建议的 HTTP 状态码
     * @param message 面向用户的中文说明
     * @throws ResponseStatusException 总是抛出，调用点无需返回
     */
    private static void fail(int code,String message){throw new ResponseStatusException(HttpStatus.valueOf(code),message);}
}
