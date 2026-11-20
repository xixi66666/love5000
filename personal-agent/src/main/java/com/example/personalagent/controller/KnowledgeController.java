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

@RestController
public class KnowledgeController {
    private final VaultService vault;private final QuartzService quartz;private final AnalysisService analyses;
    private final LocalSecurity security;private final AgentConfig config;private final HealthArchive exams;
    public KnowledgeController(VaultService vault,QuartzService quartz,AnalysisService analyses,LocalSecurity security,AgentConfig config,HealthArchive exams){this.vault=vault;this.quartz=quartz;this.analyses=analyses;this.security=security;this.config=config;this.exams=exams;}
    @GetMapping("/api/health") public Object health(){return map("success",true,"service","personal-agent");}
    @GetMapping("/api/auth/status") public Object auth(HttpServletRequest req){return ok(security.status(req));}
    @PostMapping("/api/auth/setup") public Object setup(@RequestBody Map<String,Object> body,HttpServletRequest req){security.authenticate(text(body,"password"),true,req);return auth(req);}
    @PostMapping("/api/auth/login") public Object login(@RequestBody Map<String,Object> body,HttpServletRequest req){security.authenticate(text(body,"password"),false,req);return auth(req);}
    @PostMapping("/api/auth/logout") public Object logout(HttpServletRequest req){req.getSession().invalidate();return ok(map("authenticated",false));}
    @GetMapping("/api/vault") public Object vault()throws Exception{return ok(vault.summary());}
    @PostMapping("/api/vault/connect") public Object connect(@RequestBody Map<String,Object> body)throws Exception {
        require(!analyses.busy()&&!quartz.busy()&&!exams.busy(),"请等待分析和构建完成后切换仓库");vault.connect(text(body,"path"));return vault();
    }
    @PostMapping("/api/vault/initialize") public Object initialize()throws Exception{vault.initialize();return vault();}
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
    @GetMapping("/api/note") public Object note(@RequestParam String path)throws Exception{return ok(vault.detail(path));}
    @GetMapping("/api/vault/overview") public Object overview(@RequestParam(defaultValue="") String domain)throws Exception{
        return ok(vault.overview(domain));
    }
    @PostMapping("/api/notes") public Object save(@RequestBody Map<String,Object> input)throws Exception{return ok(vault.detail(vault.save(input).path));}
    @GetMapping("/api/settings") public Object settings()throws Exception{ModelProperties.Route route=ModelProperties.load().route("personal-agent");return ok(map("data_dir",config.dataPath().toString(),"vault_dir",vault.root().toString(),"api_base",route==null?"":route.provider().baseUrl(),"model",route==null?"":route.modelId(),"quartz",quartz.status()));}
    @GetMapping("/api/quartz") public Object quartzStatus()throws Exception{return ok(quartz.status());}
    @PostMapping("/api/quartz/build") public Object build()throws Exception{return ok(quartz.build());}
    @PostMapping("/api/analyses/preview") public Object preview(@RequestBody Map<String,Object> input)throws Exception{return ok(analyses.preview(text(input,"question"),text(input,"domain"),text(input,"source_path")));}
    @PostMapping("/api/analyses") public Object analyze(@RequestBody Map<String,Object> input)throws Exception{return ok(analyses.start(input));}
    @GetMapping("/api/analyses") public Object history(){return ok(analyses.history());}
    @GetMapping({"/library","/library/**"}) public ResponseEntity<?> page(HttpServletRequest req)throws Exception {
        if(req.getRequestURI().equals("/library"))return ResponseEntity.status(302).header("Location","/library/").build();
        String relative=URLDecoder.decode(req.getRequestURI().substring("/library/".length()).replace("+","%2B"),"UTF-8");
        Path file=quartz.resolve(relative);MediaType type=MediaTypeFactory.getMediaType(file.getFileName().toString()).orElse(MediaType.APPLICATION_OCTET_STREAM);
        return ResponseEntity.ok().contentType(type).header("Cache-Control","no-store").body(new FileSystemResource(file));
    }
}
