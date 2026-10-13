package com.example.personalagent.controller;

import com.example.personalagent.AgentConfig;
import com.example.personalagent.service.*;
import com.example.personalagent.storage.Store;
import com.example.personalagent.finance.FinanceService;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.core.type.TypeReference;
import org.springframework.web.bind.annotation.*;
import java.nio.file.*;
import java.io.*;
import java.util.*;
import java.util.zip.*;
import java.util.stream.*;
import static com.example.personalagent.Api.*;

@RestController
@RequestMapping("/api/data")
public class RestoreController {
    private final Store store;private final AgentConfig config;private final VaultService vault;private final AgentController controller;private final FinanceService finance;private final ObjectMapper json;
    public RestoreController(Store store,AgentConfig config,VaultService vault,AgentController controller,FinanceService finance,ObjectMapper json){this.store=store;this.config=config;this.vault=vault;this.controller=controller;this.finance=finance;this.json=json;}
    @GetMapping("/backups") public Object list()throws Exception{Path folder=config.dataPath().resolve("backups");List<Map<String,Object>> files=new ArrayList<>();if(Files.isDirectory(folder))try(Stream<Path> paths=Files.list(folder)){for(Path p:paths.filter(f->Files.isRegularFile(f)&&!Files.isSymbolicLink(f)&&f.getFileName().toString().matches("backup-[0-9]+\\.zip")).sorted(Comparator.reverseOrder()).limit(100).collect(Collectors.toList()))files.add(map("filename",p.getFileName().toString(),"size",Files.size(p),"created_at",Files.getLastModifiedTime(p).toInstant().toString()));}return ok(map("items",files));}
    @PostMapping("/restore") public synchronized Object restore(@RequestBody Map<String,Object> request)throws Exception{
        String name=text(request,"filename");require(name.matches("backup-[0-9]+\\.zip"),"请选择本机已有备份");Path backup=config.dataPath().resolve("backups").resolve(name);require(Files.isRegularFile(backup)&&!Files.isSymbolicLink(backup),"备份不存在");
        Map<String,byte[]> entries=new LinkedHashMap<>();long total=0;int count=0;
        try(ZipInputStream input=new ZipInputStream(Files.newInputStream(backup))){ZipEntry entry;while((entry=input.getNextEntry())!=null){if(entry.isDirectory())continue;require(++count<=25000,"备份文件数量过多");String path=entry.getName();require(path.equals("state.json")||path.startsWith("vault/"),"备份格式无效");if(path.startsWith("vault/"))vault.safe(path.substring(6));require(!entries.containsKey(path),"备份包含重复路径");ByteArrayOutputStream bytes=new ByteArrayOutputStream();byte[] buffer=new byte[8192];int n;while((n=input.read(buffer))!=-1){total+=n;require(total<=250000000&&bytes.size()+n<=100000000,"备份超出恢复大小限制");bytes.write(buffer,0,n);}entries.put(path,bytes.toByteArray());}}
        require(entries.containsKey("state.json"),"备份缺少业务状态");Map<String,Map<String,Map<String,Object>>> restored=json.readValue(entries.get("state.json"),new TypeReference<Map<String,Map<String,Map<String,Object>>>>(){});require(restored.containsKey("records")||restored.containsKey("auth"),"备份业务状态无效");
        for(Map<String,Object> r:restored.getOrDefault("records",Collections.emptyMap()).values())require(r.get("id") instanceof String&&r.get("kind") instanceof String&&r.get("content") instanceof String&&r.get("revision") instanceof Number&&r.get("payload") instanceof Map,"备份记录格式无效");
        Object safetyBackup=controller.backup();Map<String,Object> result;
        synchronized(vault){synchronized(store){
            require(store.list("jobs").stream().noneMatch(j->"running".equals(j.get("status"))),"请等待当前AI任务结束后恢复");List<Map<String,Object>> oldPublication=store.list("publish");
            Map<String,Map<String,Object>> deletions=new LinkedHashMap<>(restored.getOrDefault("deletions",Collections.emptyMap()));for(Map<String,Object> d:store.list("deletions"))deletions.put(text(d,"id"),d);restored.put("deletions",deletions);
            Map<String,Map<String,Object>> exclusions=new LinkedHashMap<>(restored.getOrDefault("exclusions",Collections.emptyMap()));for(Map.Entry<String,Map<String,Object>> e:store.snapshot().getOrDefault("exclusions",Collections.emptyMap()).entrySet())exclusions.put(e.getKey(),e.getValue());restored.put("exclusions",exclusions);
            Set<String> removed=new HashSet<>();for(Map<String,Object> d:deletions.values())if("source".equals(d.get("kind")))removed.add(text(d,"id"));Map<String,Map<String,Object>> records=restored.getOrDefault("records",new LinkedHashMap<>());boolean changed;do{changed=false;for(Map<String,Object> r:records.values()){Map<String,Object> payload=(Map<String,Object>)r.get("payload");boolean linked=removed.contains(text(r,"entity_id"));Object sources=payload.get("source_ids");if(sources instanceof List)for(Object s:(List)sources)linked|=removed.contains(String.valueOf(s));if(linked&&removed.add(text(r,"id")))changed=true;}}while(changed);records.keySet().removeAll(removed);
            Map<String,Map<String,Object>> publish=restored.getOrDefault("publish",new LinkedHashMap<>());for(String id:removed){Map<String,Object> p=publish.remove(id);if(p!=null)entries.remove("vault/"+text(p,"path").replace('\\','/'));}
            for(String collection:Arrays.asList("memories","chunks","sources","notifications","jobs","triggers"))restored.getOrDefault(collection,new LinkedHashMap<>()).entrySet().removeIf(e->{Map<String,Object> value=e.getValue();boolean deleted=removed.contains(text(value,"source_id"))||removed.contains(text(value,"record_id"))||removed.contains(text(value,"conversation_id"))||deletions.containsKey(e.getKey());Object payload=value.get("payload");if(payload instanceof Map){deleted|=removed.contains(text((Map<String,Object>)payload,"source_id"));Object sources=((Map)payload).get("source_ids");if(sources instanceof List)for(Object s:(List)sources)deleted|=removed.contains(String.valueOf(s));}return deleted;});
            for(Map<String,Object> job:restored.getOrDefault("jobs",Collections.emptyMap()).values())if("running".equals(job.get("status")))job.put("status","queued");RecordService.revision(restored);
            // Prepare all replacement files before committing; the pre-restore archive remains available on failure.
            Path stage=Files.createTempDirectory(config.dataPath(),"restore-");List<Path> staged=new ArrayList<>();try{for(Map.Entry<String,byte[]> e:entries.entrySet())if(e.getKey().startsWith("vault/")){String relative=e.getKey().substring(6);Path file=stage.resolve(relative).normalize();require(file.startsWith(stage),"恢复路径越界");Files.createDirectories(file.getParent());Files.write(file,e.getValue());staged.add(file);}store.mutate(all->{all.clear();all.putAll(restored);});for(Map<String,Object> p:oldPublication)if(!records.containsKey(text(p,"record_id"))&&!text(p,"path").isEmpty())Files.deleteIfExists(vault.safe(text(p,"path")));for(Path file:staged){Path destination=vault.safe(stage.relativize(file).toString());Files.createDirectories(destination.getParent());try{Files.move(file,destination,StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE);}catch(AtomicMoveNotSupportedException e){Files.move(file,destination,StandardCopyOption.REPLACE_EXISTING);}}vault.flush();}finally{try(Stream<Path> paths=Files.walk(stage)){for(Path p:paths.sorted(Comparator.reverseOrder()).collect(Collectors.toList()))Files.deleteIfExists(p);}}
            result=map("restored",true,"filename",name,"safety_backup",safetyBackup,"deleted_sources_suppressed",removed.size());
        }}
        finance.invalidateCache();return ok(result);
    }
}
