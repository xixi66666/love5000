package com.example.personalagent.controller;

import com.example.personalagent.*;
import com.example.personalagent.service.*;
import com.example.personalagent.security.LocalSecurity;
import com.example.personalagent.storage.Store;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.web.bind.annotation.*;
import javax.servlet.http.HttpServletRequest;
import java.util.*;
import java.nio.file.*;
import java.io.*;
import java.util.zip.*;
import java.util.stream.*;
import static com.example.personalagent.Api.*;

@RestController
@RequestMapping("/api")
public class AgentController {
    private final Store store;private final RecordService records;private final AgentService agent;private final KnowledgeService knowledge;private final VaultService vault;private final LocalSecurity security;private final AgentConfig config;private final ObjectMapper json;
    public AgentController(Store store,RecordService records,AgentService agent,KnowledgeService knowledge,VaultService vault,LocalSecurity security,AgentConfig config,ObjectMapper json){this.store=store;this.records=records;this.agent=agent;this.knowledge=knowledge;this.vault=vault;this.security=security;this.config=config;this.json=json;}
    @GetMapping("/health") public Object health(){return map("success",true,"service","personal-agent");}
    @GetMapping("/auth/status") public Object auth(HttpServletRequest req){return ok(security.status(req));}
    @PostMapping("/auth/setup") public Object setup(@RequestBody Map<String,Object> body,HttpServletRequest req){security.authenticate(text(body,"password"),true,req);return auth(req);}
    @PostMapping("/auth/login") public Object login(@RequestBody Map<String,Object> body,HttpServletRequest req){security.authenticate(text(body,"password"),false,req);return auth(req);}
    @PostMapping("/auth/logout") public Object logout(HttpServletRequest req){req.getSession().invalidate();return ok(map("authenticated",false));}
    @GetMapping("/settings") public Object settings(){return ok(map("data_dir",config.dataPath().toString(),"vault_dir",config.vaultPath().toString(),"model_configured",agent.configured(),"model",agent.model(),"api_base",agent.base(),"settings",agent.settings()));}
    @PatchMapping("/settings") public Object patchSettings(@RequestBody Map<String,Object> data){Object nested=data.get("settings");return ok(agent.saveSettings(nested instanceof Map?(Map<String,Object>)nested:data));}
    @GetMapping("/timeline") public Object timeline(@RequestParam(required=false)String kind,@RequestParam(required=false)String entity_id,@RequestParam(required=false)String q,@RequestParam(defaultValue="50")int limit,@RequestParam(required=false)String cursor,@RequestParam(defaultValue="false")boolean archived){return ok(records.list(kind,entity_id,q,limit,cursor,archived));}
    @GetMapping({"/records/{id}","/ideas/{id}","/books/{id}"}) public Object getRecord(@PathVariable String id){Map<String,Object> r=records.get(id);r.put("publication",store.get("publish",id));return ok(r);}
    @PatchMapping({"/records/{id}","/notes/{id}","/ideas/{id}","/actions/{id}"}) public Object update(@PathVariable String id,@RequestBody Map<String,Object> data){Map<String,Object> r=records.update(id,data);if(data.containsKey("content")&&Arrays.asList("life","reading","insight").contains(r.get("kind"))&&Boolean.TRUE.equals(agent.settings().get("auto_memory")))agent.job("memory",map("content",r.get("content"),"source_id",r.get("id")),"memory:"+r.get("id")+":"+r.get("revision"));vault.flush();return ok(r);}
    @DeleteMapping({"/records/{id}","/notes/{id}","/ideas/{id}","/books/{id}"}) public Object delete(@PathVariable String id){records.delete(id);vault.flush();return ok(map("deleted",true));}
    @GetMapping("/notes") public Object notes(@RequestParam(defaultValue="50")int limit,@RequestParam(required=false)String cursor){return ok(records.list("life,insight,reading",null,null,limit,cursor,false));}
    @PostMapping("/notes") public Object note(@RequestBody Map<String,Object> data){String kind=text(data,"kind");if(kind.isEmpty())kind="life";require(Arrays.asList("life","insight","reading").contains(kind),"记录类型无效");Map<String,Object> r=records.create(kind,data,text(data,"book_id").isEmpty()?null:text(data,"book_id"),"active");if(Boolean.TRUE.equals(agent.settings().get("auto_memory")))agent.job("memory",map("content",r.get("content"),"source_id",r.get("id")),"memory:"+r.get("id"));vault.flush();return ok(r);}
    @GetMapping("/ideas") public Object ideas(@RequestParam(defaultValue="50")int limit,@RequestParam(required=false)String cursor){return ok(records.list("idea",null,null,limit,cursor,false));}
    @PostMapping("/ideas") public Object idea(@RequestBody Map<String,Object> data){Map<String,Object> r=records.create("idea",data,null,"inbox");vault.flush();return ok(r);}
    @PostMapping("/ideas/{id}/activate") public Object activate(@PathVariable String id,@RequestBody(required=false)Map<String,Object> body){Map<String,Object> r=records.get(id);require("idea".equals(r.get("kind")),"请选择想法");Map<String,Object> data=body==null?new LinkedHashMap<>():new LinkedHashMap<>(body);data.putIfAbsent("expected_revision",r.get("revision"));data.put("status","validating");return update(id,data);}
    @PostMapping("/ideas/{id}/events") public Object progress(@PathVariable String id,@RequestBody Map<String,Object> data){Map<String,Object> idea=records.get(id);require("idea".equals(idea.get("kind"))&&!"inbox".equals(idea.get("status")),"请先选择推进此想法");String kind=text(data,"event_type");require(Arrays.asList("progress","result").contains(kind),"记录类型应为进展或结果");Map<String,Object> input=new LinkedHashMap<>(data);input.putIfAbsent("title",("result".equals(kind)?"验证结果：":"行动进展：")+text(idea,"title"));if("result".equals(kind)){String outcome=text(data,"outcome");if(outcome.isEmpty())outcome="unverified";require(Arrays.asList("unverified","inconclusive","succeeded","failed").contains(outcome),"结果状态无效");if(Arrays.asList("succeeded","failed").contains(outcome))require(!text(data,"evidence").trim().isEmpty(),"确认结果需要证据");input.put("outcome",outcome);}input.put("important",true);Map<String,Object> r=records.create(kind,input,id,"active");vault.flush();return ok(r);}
    @GetMapping("/ideas/{id}/events") public Object events(@PathVariable String id){return ok(records.list("progress,result,change",id,null,100,null,true));}
    @GetMapping("/actions") public Object actions(@RequestParam(required=false)String idea_id,@RequestParam(required=false)String entity_id){return ok(records.list("action",idea_id==null?entity_id:idea_id,null,100,null,false));}
    @GetMapping("/ideas/{id}/actions") public Object ideaActions(@PathVariable String id){return ok(records.list("action",id,null,100,null,false));}
    @PostMapping("/ideas/{id}/actions") public Object action(@PathVariable String id,@RequestBody Map<String,Object> data){Map<String,Object> parent=records.get(id);require("idea".equals(parent.get("kind"))&&!"inbox".equals(parent.get("status")),"请先推进想法");Map<String,Object> input=new LinkedHashMap<>(data);if(data.containsKey("due_at"))input.put("due_at",RecordService.time(data.get("due_at")));Map<String,Object> r=records.create("action",input,id,"open");vault.flush();return ok(r);}
    @GetMapping("/books") public Object books(){return ok(records.list("book",null,null,100,null,false));}
    @GetMapping("/books/skills") public Object skills(){return ok(map("items",knowledge.skills()));}
    @PostMapping("/books") public Object book(@RequestBody Map<String,Object> data)throws Exception{return ok(knowledge.importBook(data));}
    @PostMapping("/search") public Object search(@RequestBody Map<String,Object> data){return ok(map("items",knowledge.search(text(data,"query"),10)));}
    @GetMapping("/memories") public Object memories(){return ok(map("items",store.list("memories")));}
    @PatchMapping("/memories/{id}") public Object memory(@PathVariable String id,@RequestBody Map<String,Object> data){return ok(agent.updateMemory(id,data));}
    @DeleteMapping("/memories/{id}") public Object forget(@PathVariable String id){agent.deleteMemory(id);return ok(map("deleted",true));}
    @PostMapping("/chat/messages") public Object chat(@RequestBody Map<String,Object> data){return ok(agent.chat(data));}
    @GetMapping("/conversations") public Object conversations(){return ok(records.list("conversation",null,null,100,null,false));}
    @GetMapping("/conversations/{id}/messages") public Object messages(@PathVariable String id){return ok(records.list("message",id,null,100,null,true));}
    @GetMapping("/jobs/{id}") public Object job(@PathVariable String id){return ok(agent.getJob(id));}
    @PostMapping("/jobs/{id}/retry") public Object retry(@PathVariable String id){agent.retry(id);return job(id);}
    @GetMapping("/jobs") public Object jobs(){List<Map<String,Object>> result=new ArrayList<>();for(Map<String,Object> j:store.list("jobs")){j.remove("payload");result.add(j);}return ok(map("items",result));}
    @GetMapping("/reviews") public Object reviews(){return ok(records.list("review,finance_review",null,null,100,null,false));}
    @PostMapping("/reviews/request") public Object requestReview(@RequestBody(required=false)Map<String,Object> data){List<String> ids=new ArrayList<>();if(data!=null&&data.get("source_ids") instanceof List)for(Object id:(List)data.get("source_ids")){records.get(String.valueOf(id));ids.add(String.valueOf(id));}if(ids.isEmpty())for(Map<String,Object> r:(List<Map<String,Object>>)records.list(null,null,null,20,null,false).get("items"))if(!"message".equals(r.get("kind")))ids.add(text(r,"id"));Map<String,Object> job=agent.job("review",map("source_ids",ids,"entity_id","manual-review","content",data==null?"":text(data,"content")),null);return ok(map("job_id",job.get("id")));}
    @GetMapping("/notifications") public Object notifications(){List<Map<String,Object>> all=store.list("notifications");return ok(map("items",all,"unread_count",all.stream().filter(n->n.get("read_at")==null).count()));}
    @PostMapping("/reviews/{id}/read") public Object readReview(@PathVariable String id){records.get(id);for(Map<String,Object> n:store.list("notifications"))if(id.equals(n.get("record_id"))){n.put("read_at",now());store.put("notifications",text(n,"id"),n);}return ok(map("read",true));}
    @PostMapping("/notifications/{id}/read") public Object read(@PathVariable String id){Map<String,Object> n=store.get("notifications",id);require(n!=null,"提醒不存在");n.put("read_at",now());store.put("notifications",id,n);return ok(n);}
    @GetMapping("/data/status") public Object status(){List<Map<String,Object>> publish=store.list("publish"),jobs=store.list("jobs");return ok(map("data_dir",config.dataPath().toString(),"vault_dir",config.vaultPath().toString(),"records",store.list("records").size(),"memories",store.list("memories").size(),"pending_jobs",jobs.stream().filter(j->Arrays.asList("queued","running","waiting_configuration").contains(j.get("status"))).count(),"publish_pending",publish.stream().filter(p->"pending".equals(p.get("state"))).count(),"conflicts",publish.stream().filter(p->"conflict".equals(p.get("state"))).collect(Collectors.toList()),"current_conflicts",store.list("current_publish").stream().filter(p->"conflict".equals(p.get("state"))).collect(Collectors.toList()),"source_missing",0,"fts_enabled",false,"index_type","本地关键词检索","last_backup",store.get("meta","last_backup")));}
    @PostMapping("/data/reindex") public Object reindex()throws Exception{return ok(knowledge.reindex());}
    @PostMapping("/data/conflicts/{id}/resolve") public Object resolve(@PathVariable String id,@RequestBody Map<String,Object> data)throws Exception{return ok(vault.resolve(id,!Boolean.FALSE.equals(data.get("keep_manual"))));}
    @PostMapping("/data/backup") public synchronized Object backup()throws Exception { synchronized(vault){synchronized(store){
        vault.flush();Path root=config.dataPath().resolve("backups");Files.createDirectories(root);String name="backup-"+System.currentTimeMillis()+".zip";Path temp=root.resolve(name+".tmp"),target=root.resolve(name);Map<String,Map<String,Map<String,Object>>> snapshot=store.snapshot();
        try(ZipOutputStream zip=new ZipOutputStream(Files.newOutputStream(temp))){zip.putNextEntry(new ZipEntry("state.json"));zip.write(json.writeValueAsBytes(snapshot));zip.closeEntry();try(Stream<Path> files=Files.walk(config.vaultPath())){for(Path file:files.filter(p->Files.isRegularFile(p)&&!Files.isSymbolicLink(p)&&!p.getFileName().toString().endsWith(".tmp")).collect(Collectors.toList())){Path safe=vault.safe(config.vaultPath().relativize(file).toString());zip.putNextEntry(new ZipEntry("vault/"+config.vaultPath().relativize(safe).toString().replace('\\','/')));Files.copy(safe,zip);zip.closeEntry();}}}Files.move(temp,target,StandardCopyOption.REPLACE_EXISTING);Map<String,Object> result=map("filename",name,"path",target.toString(),"created_at",now(),"size",Files.size(target));store.put("meta","last_backup",result);return ok(result);}}
    }
}
