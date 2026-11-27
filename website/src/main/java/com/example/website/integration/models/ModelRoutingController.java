package com.example.website.integration.models;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import javax.servlet.http.*;
import java.net.*;
import java.util.*;
import com.example.website.integration.local.LocalServicesManager;

/**
 * 统一模型网关的 HTTP 入口，前缀 {@code /api/models}。
 *
 * <p>属于 integration/models 的 Web 层：目录探测、手动刷新、单服务选择、生效状态查询，
 * 以及两条生成代理 {@code /chat/{scope}}（兼容旧调用）与 {@code /complete/{scope}}
 * （服务端调用，204 表示使用服务原配置）。业务规则全部在 {@link ModelRoutingService}，
 * 这里只做来源校验与响应状态选择。</p>
 *
 * <p>安全边界：只允许回环地址与 localhost、127.0.0.1、::1 的 Host；带 Origin 的请求必须
 * 指向允许的本机端口；写操作还要求自定义头 {@code X-Love530-Model: 1}；生成接口拒绝任何
 * 带 Origin 的浏览器请求，密钥因此不会出现在浏览器发起的请求链路上。类级
 * {@code @CrossOrigin} 的允许来源必须与 guard 中的判断保持一致，因为真实的 OPTIONS
 * 预检由 Spring MVC 在进入方法前处理。</p>
 */
@RestController
@RequestMapping("/api/models")
// 真实浏览器预检在进入控制器方法前由 Spring MVC 处理，必须声明同一份受限本机来源。
@CrossOrigin(origins={
        "http://127.0.0.1:8080","http://localhost:8080","http://[::1]:8080",
        "http://127.0.0.1:5174","http://localhost:5174","http://[::1]:5174",
        "http://127.0.0.1:5176","http://localhost:5176","http://[::1]:5176",
        "http://127.0.0.1:5177","http://localhost:5177","http://[::1]:5177",
        "http://127.0.0.1:5178","http://localhost:5178","http://[::1]:5178"
},methods={RequestMethod.GET,RequestMethod.PUT,RequestMethod.POST,RequestMethod.OPTIONS},
        allowedHeaders={"Content-Type","X-Love530-Model"},allowCredentials="false",maxAge=600)
public class ModelRoutingController {
    private final ModelRoutingService service;
    private final LocalServicesManager local;
    public ModelRoutingController(ModelRoutingService service,LocalServicesManager local){this.service=service;this.local=local;}
    /**
     * 读取模型目录与当前选择。
     *
     * @param req 用于来源校验
     * @param res 用于写入 CORS 与禁缓存响应头
     * @return 含 {@code success}、探测时间 {@code checkedAt}、模型列表 {@code models}、
     *         各服务已选模型 {@code selections} 与可选服务清单 {@code services} 的响应表
     */
    @GetMapping public Map<String,Object> catalog(HttpServletRequest req,HttpServletResponse res){guard(req,res,false);return service.catalog(false);}
    /**
     * 强制重新探测模型目录，对应选择器上的刷新按钮。
     *
     * <p>属于写操作，需要通过本机来源校验并携带 {@code X-Love530-Model: 1}；探测使用独立锁，
     * 不会阻塞正在进行的生成请求。</p>
     *
     * @param req 用于来源校验
     * @param res 用于写入 CORS 与禁缓存响应头
     * @return 刷新后的目录，结构同 {@code GET /api/models}
     */
    @PostMapping("/refresh") public Map<String,Object> refresh(HttpServletRequest req,HttpServletResponse res){guard(req,res,true);return service.catalog(true);}
    /**
     * 启动本机 Strata 服务后重新探测目录，供选择器在模型未开机时一键拉起。
     *
     * @param req 用于来源校验
     * @param res 用于写入 CORS 与禁缓存响应头
     * @return 刷新后的目录
     */
    @PostMapping("/local/strata/start") public Map<String,Object> startLocal(HttpServletRequest req,HttpServletResponse res){guard(req,res,true);local.action("strata","start");return service.catalog(true);}
    /**
     * 查询某个服务当前生效的模型。
     *
     * @param scope 服务标识：global、python-a、scrapling-ui、skill-finder、personal-agent
     * @param req   用于来源校验
     * @param res   用于写入 CORS 与禁缓存响应头
     * @return {@code selection}（本服务显式选择，空串表示未选）、{@code modelId}（继承后的
     *         实际模型）、{@code active}（是否启用统一模型）、{@code inherited}
     *         （是否继承全局选择）
     */
    @GetMapping("/effective/{scope}") public Map<String,Object> effective(@PathVariable String scope,HttpServletRequest req,HttpServletResponse res){guard(req,res,false);return service.effective(scope);}
    /**
     * 设置或清除某个服务的模型选择。
     *
     * <p>请求体只取 {@code modelId}：空串表示清除并回退到继承或服务原配置，{@code native}
     * 表示显式使用服务原配置。非空选择必须是目录中已验证可用的模型，否则返回 409，
     * 避免持久化一个永远无法生成的选项。</p>
     *
     * @param scope 服务标识
     * @param body  请求体，仅使用 {@code modelId}
     * @param req   用于来源校验
     * @param res   用于写入 CORS 与禁缓存响应头
     * @return 保存后的生效状态
     */
    @PutMapping("/selection/{scope}") public Map<String,Object> select(@PathVariable String scope,@RequestBody Map<String,String> body,HttpServletRequest req,HttpServletResponse res){guard(req,res,true);return service.select(scope,body.get("modelId"));}
    /**
     * 兼容旧调用方的文本生成代理。
     *
     * <p>拒绝带 Origin 的请求：生成接口只允许服务端调用，浏览器页面不能把它当作免费代理。
     * 该服务未启用统一模型时返回 409，由调用方回退到自己的原配置。</p>
     *
     * @param scope 服务标识，不能是 {@code global}
     * @param body  OpenAI 兼容请求体，只接受文本消息
     * @param req   用于来源校验
     * @param res   用于写入 CORS 与禁缓存响应头
     * @return 上游 chat completions 的原始响应
     */
    @PostMapping("/chat/{scope}") public JsonNode chat(@PathVariable String scope,@RequestBody ObjectNode body,HttpServletRequest req,HttpServletResponse res){guard(req,res,true);if(req.getHeader("Origin")!=null)throw new ResponseStatusException(HttpStatus.FORBIDDEN,"生成接口仅限服务端调用");return service.chat(scope,body);}
    /**
     * 服务端使用的文本生成入口。
     *
     * <p>与 {@code /chat} 的区别在于「明确使用原配置」的表达：返回 204 且无响应体，表示该
     * 服务当前没有启用统一模型，调用方应继续使用自己的模型配置；返回 200 时响应体即上游
     * 结果。超时与 HTTP 错误不会被折叠成 204，避免把网络故障误判成「无统一选择」。</p>
     *
     * @param scope 服务标识，不能是 {@code global}
     * @param body  OpenAI 兼容请求体，只接受文本消息
     * @param req   用于来源校验
     * @param res   用于写入 CORS 与禁缓存响应头
     * @return 200 加模型结果；或 204 表示使用服务原配置
     */
    @PostMapping("/complete/{scope}")
    public ResponseEntity<JsonNode> complete(@PathVariable String scope,@RequestBody ObjectNode body,HttpServletRequest req,HttpServletResponse res) {
        guard(req,res,true);
        if(req.getHeader("Origin")!=null)throw new ResponseStatusException(HttpStatus.FORBIDDEN,"生成接口仅限服务端调用");
        JsonNode result=service.complete(scope,body);
        return result==null?ResponseEntity.noContent().build():ResponseEntity.ok(result);
    }
    /**
     * 显式处理 OPTIONS 预检请求。
     *
     * <p>真实浏览器的预检由框架在进入控制器前处理，这里再写一次允许的方法与请求头，
     * 覆盖不带 Origin 的直接探测；不依赖注解默认值，避免与实际允许列表漂移。</p>
     *
     * @param req 用于来源校验
     * @param res 用于写入预检响应头
     * @return 204 空响应
     */
    @RequestMapping(value={"","/**"},method=RequestMethod.OPTIONS)
    public ResponseEntity<Void> options(HttpServletRequest req,HttpServletResponse res){guard(req,res,false);res.setHeader("Access-Control-Allow-Methods","GET, PUT, POST, OPTIONS");res.setHeader("Access-Control-Allow-Headers","Content-Type, X-Love530-Model");res.setHeader("Access-Control-Max-Age","600");return ResponseEntity.noContent().build();}
    /**
     * 校验请求来源，并把 CORS 与禁缓存响应头写进响应。
     *
     * <p>条件：远端地址为回环地址；Host 为 localhost、127.0.0.1 或 ::1；带 Origin 时必须是
     * http 且指向本机允许端口（8080、5174、5176、5177、5178 或当前服务端口）；写操作必须带
     * {@code X-Love530-Model: 1}。失败统一抛 403，不区分具体原因。成功时回写
     * {@code Access-Control-Allow-Origin} 与 {@code Vary: Origin}，并始终设置
     * {@code Cache-Control: no-store}，防止目录和选择被中间层缓存。</p>
     *
     * @param req   当前请求
     * @param res   当前响应
     * @param write 是否为写操作
     * @throws ResponseStatusException 任一条件不满足时抛出 403
     */
    static void guard(HttpServletRequest req,HttpServletResponse res,boolean write) {
        try {
            if(!InetAddress.getByName(req.getRemoteAddr()).isLoopbackAddress() || !local(req.getServerName())) throw new Exception();
            String origin=req.getHeader("Origin");
            if(origin!=null) {
                URI uri=URI.create(origin);int port=uri.getPort();
                if(!local(uri.getHost()) || !"http".equals(uri.getScheme()) || !(port==req.getServerPort() || Arrays.asList(8080,5174,5176,5177,5178).contains(port))) throw new Exception();
                res.setHeader("Access-Control-Allow-Origin",origin);res.setHeader("Vary","Origin");
            }
            if(write && !"1".equals(req.getHeader("X-Love530-Model"))) throw new Exception();
            res.setHeader("Cache-Control","no-store");
        } catch(Exception e){throw new ResponseStatusException(HttpStatus.FORBIDDEN,"请通过本机服务页面管理模型");}
    }
    private static boolean local(String h){return "localhost".equalsIgnoreCase(h)||"127.0.0.1".equals(h)||"::1".equals(h)||"[::1]".equals(h);}
    /**
     * 把路由异常映射成统一的失败响应。
     *
     * <p>只回传固定中文原因，不回传异常堆栈或上游细节。</p>
     *
     * @param e 带状态码的异常
     * @return {@code success=false} 与可读 {@code message}
     */
    @ExceptionHandler(ResponseStatusException.class)
    public ResponseEntity<Map<String,Object>> error(ResponseStatusException e){Map<String,Object> body=new LinkedHashMap<>();body.put("success",false);body.put("message",e.getReason());return ResponseEntity.status(e.getStatus()).body(body);}
}
