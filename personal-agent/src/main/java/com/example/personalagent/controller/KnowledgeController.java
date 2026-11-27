package com.example.personalagent.controller;

import com.example.personalagent.*;
import com.example.common.ai.ModelProperties;
import com.example.personalagent.model.VaultNote;
import com.example.personalagent.service.*;
import com.example.personalagent.security.LocalSecurity;
import org.springframework.web.bind.annotation.*;
import org.springframework.http.*;
import org.springframework.core.io.*;
import javax.servlet.http.HttpServletRequest;
import java.util.*;
import java.nio.file.*;
import java.net.URLDecoder;
import java.util.stream.Collectors;
import static com.example.personalagent.Api.*;

/**
 * 资料库的 HTTP 门面：把认证、Vault 读写、Quartz 快照、AI 分析与健康档案汇聚到同一组
 * 路由上（{@code /api/} 前缀与 {@code /library/} 私人浏览页）。
 *
 * <p>属 Controller 层，只负责入参形状校验、并发前置判断与响应包装；路径约束、乐观锁、
 * 内容哈希与构建流程分别在 {@link VaultService}、{@link QuartzService}、
 * {@link AnalysisService}、{@link HealthArchive} 中实现，本类不直接碰文件系统。</p>
 *
 * <p>非显然行为：{@code /api/health} 与三个 {@code /api/auth/} 接口放行匿名访问——前者供首页 no-cors 探活，后者只处理登录本身；
 * 切换仓库前先确认分析、Quartz 构建、体检解读三者都不在运行，避免后台任务把结果写进
 * 另一份资料；{@code /library/} 下每个响应都带 {@code no-store}，产物不会留在浏览器缓存；
 * 分析提交是异步的，接口返回任务对象而非最终报告。</p>
 */
@RestController
public class KnowledgeController {
    private final VaultService vault;private final QuartzService quartz;private final AnalysisService analyses;
    private final LocalSecurity security;private final AgentConfig config;private final HealthArchive exams;
    public KnowledgeController(VaultService vault,QuartzService quartz,AnalysisService analyses,LocalSecurity security,AgentConfig config,HealthArchive exams){this.vault=vault;this.quartz=quartz;this.analyses=analyses;this.security=security;this.config=config;this.exams=exams;}
    /** 统一健康检查：返回固定服务标识，供首页探活与巡检脚本使用，无需登录。 */
    @GetMapping("/api/health") public Object health(){return map("success",true,"service","personal-agent");}
    /** 登录状态与 CSRF 令牌；未登录时 {@code csrf_token} 为 {@code null}。 */
    @GetMapping("/api/auth/status") public Object auth(HttpServletRequest req){return ok(security.status(req));}
    /** 首次设置密码；凭据已存在时返回 409，密码规则与哈希方式见 {@link LocalSecurity}。 */
    @PostMapping("/api/auth/setup") public Object setup(@RequestBody Map<String,Object> body,HttpServletRequest req){security.authenticate(text(body,"password"),true,req);return auth(req);}
    /** 密码登录；失败次数按来源地址限流，连续超限返回 429。 */
    @PostMapping("/api/auth/login") public Object login(@RequestBody Map<String,Object> body,HttpServletRequest req){security.authenticate(text(body,"password"),false,req);return auth(req);}
    /** 作废当前 Session；CSRF 令牌随会话一起失效，前端需重新登录。 */
    @PostMapping("/api/auth/logout") public Object logout(HttpServletRequest req){req.getSession().invalidate();return ok(map("authenticated",false));}
    /** 当前 Vault 摘要：路径、笔记数、各领域计数、AI 可用篇数与资料指纹。 */
    @GetMapping("/api/vault") public Object vault()throws Exception{return ok(vault.summary());}
    /**
     * 切换到另一份已存在的 Obsidian 仓库。
     *
     * @param body {@code path} 指向包含 {@code .obsidian} 的目录
     * @return 切换后的 Vault 摘要
     * @throws Exception 目录无效、根目录是符号链接，或分析/构建/解读正在运行时抛出 422
     */
    @PostMapping("/api/vault/connect") public Object connect(@RequestBody Map<String,Object> body)throws Exception {
        require(!analyses.busy()&&!quartz.busy()&&!exams.busy(),"请等待分析和构建完成后切换仓库");vault.connect(text(body,"path"));return vault();
    }
    /** 在空仓库里补齐领域目录、模板、导航 Bases 与说明笔记；可重复执行且不覆盖既有文件。 */
    @PostMapping("/api/vault/initialize") public Object initialize()throws Exception{vault.initialize();return vault();}
    /**
     * 关键字检索笔记并分页。
     *
     * <p>每次请求都重新扫描文件系统，没有独立索引，因此外部编辑与刚导入的资料立刻可见；
     * 代价是仓库越大响应越慢。列表只回传前 180 个字符，避免把整篇正文塞进响应。</p>
     *
     * @param q      关键字，大小写不敏感地匹配标题与正文，最长 300 字符，空串表示不过滤
     * @param domain 领域 slug，空串表示全部领域
     * @param offset 跳过条数，必须非负；超过总数时返回空页而不是报错
     * @param limit  单页条数，取值 1–100
     * @return {@code items/total/offset/limit}，其中 {@code total} 是过滤后的总数
     * @throws Exception 参数越界返回 422；Vault 不可读时向上抛出
     */
    @GetMapping("/api/notes") public Object notes(@RequestParam(defaultValue="")String q,@RequestParam(defaultValue="")String domain,
        @RequestParam(defaultValue="0")int offset,@RequestParam(defaultValue="40")int limit)throws Exception {
        require(q.length()<=300&&offset>=0&&limit>=1&&limit<=100,"分页或查询参数无效");
        List<VaultNote> all=vault.notes().stream().filter(n->domain.isEmpty()||n.domain.equals(domain))
            .filter(n->q.isEmpty()||(n.title+"\n"+n.body).toLowerCase(Locale.ROOT).contains(q.toLowerCase(Locale.ROOT))).collect(Collectors.toList());
        List<Object> rows=new ArrayList<>();
        for(VaultNote n:all.subList(Math.min(offset,all.size()),(int)Math.min((long)offset+limit,all.size())))rows.add(map("path",n.path,"title",n.title,"domain",n.domain,"revision",n.revision,
            "properties",n.properties,"modified_at",n.modifiedAt,"preview",n.body.substring(0,Math.min(180,n.body.length()))));
        return ok(map("items",rows,"total",all.size(),"offset",offset,"limit",limit));
    }
    /** 单篇笔记详情：正文、属性、安全渲染后的 HTML、出链与反链，见 {@link VaultService#detail}。 */
    @GetMapping("/api/note") public Object note(@RequestParam String path)throws Exception{return ok(vault.detail(path));}
    /**
     * 工作台总览：最近笔记、最多 48 个节点及其间的双链边、近半年每月编辑数。
     *
     * @param domain 领域 slug；空串取全库。健康领域会额外纳入体检解读草稿
     * @return {@code recent/nodes/edges/edits/total}；{@code total} 只统计该领域内的笔记
     * @throws Exception 领域 slug 不存在时返回 422
     */
    @GetMapping("/api/vault/overview") public Object overview(@RequestParam(defaultValue="") String domain)throws Exception{
        return ok(vault.overview(domain));
    }
    /**
     * 保存或新建一篇 Markdown 笔记。
     *
     * <p>{@code expected_revision} 与磁盘内容不一致时返回 409 并保留外部修改，
     * 这是本模块「禁止静默覆盖 Obsidian 编辑」的落点。</p>
     */
    @PostMapping("/api/notes") public Object save(@RequestBody Map<String,Object> input)throws Exception{return ok(vault.detail(vault.save(input).path));}
    /** 设置页数据：数据目录、Vault 路径、当前模型路由与 Quartz 状态；不返回任何密钥。 */
    @GetMapping("/api/settings") public Object settings()throws Exception{ModelProperties.Route route=ModelProperties.load().route("personal-agent");return ok(map("data_dir",config.dataPath().toString(),"vault_dir",vault.root().toString(),"api_base",route==null?"":route.provider().baseUrl(),"model",route==null?"":route.modelId(),"quartz",quartz.status()));}
    /** Quartz 快照状态：依赖是否已安装、快照是否与当前资料一致、构建进度。 */
    @GetMapping("/api/quartz") public Object quartzStatus()throws Exception{return ok(quartz.status());}
    /** 异步触发一次 Quartz 构建；构建期间重复调用只返回当前状态，不会排队第二次。 */
    @PostMapping("/api/quartz/build") public Object build()throws Exception{return ok(quartz.build());}
    /** 分析前的资料检索与预览：返回候选来源片段与截断标记，不调用模型。 */
    @PostMapping("/api/analyses/preview") public Object preview(@RequestBody Map<String,Object> input)throws Exception{return ok(analyses.preview(text(input,"question"),text(input,"domain"),text(input,"source_path")));}
    /** 提交一次 AI 分析任务；入队后立即返回任务对象，结果通过 {@link #history()} 轮询。 */
    @PostMapping("/api/analyses") public Object analyze(@RequestBody Map<String,Object> input)throws Exception{return ok(analyses.start(input));}
    /** 分析任务列表，最新在前；服务重启后残留的运行中任务会被标记为 {@code interrupted}。 */
    @GetMapping("/api/analyses") public Object history(){return ok(analyses.history());}
    /**
     * 提供 Quartz 生成的私人浏览页。
     *
     * <p>{@code /library} 无尾斜杠时先重定向，保证页面内的相对链接可用；快照与当前资料
     * 指纹不一致时由 {@link QuartzService#resolve(String)} 直接 409，避免把旧资料当现状
     * 展示。响应一律 {@code no-store}，内容不进入浏览器缓存。</p>
     *
     * @param req 原始请求；URI 去掉 {@code /library/} 前缀并解码后即站点内相对路径，
     *            加号按字面量处理，避免路径里的 {@code +} 被解成空格
     * @return 按扩展名推断 Content-Type 的文件内容，未知类型退回八位字节流
     * @throws Exception 快照过期、路径越界或文件不存在时抛出
     */
    @GetMapping({"/library","/library/**"}) public ResponseEntity<?> page(HttpServletRequest req)throws Exception {
        if(req.getRequestURI().equals("/library"))return ResponseEntity.status(302).header("Location","/library/").build();
        String relative=URLDecoder.decode(req.getRequestURI().substring("/library/".length()).replace("+","%2B"),"UTF-8");
        Path file=quartz.resolve(relative);MediaType type=MediaTypeFactory.getMediaType(file.getFileName().toString()).orElse(MediaType.APPLICATION_OCTET_STREAM);
        return ResponseEntity.ok().contentType(type).header("Cache-Control","no-store").body(new FileSystemResource(file));
    }
}
