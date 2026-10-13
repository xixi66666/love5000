package com.example.personalagent.service;

import com.example.personalagent.Api;
import com.example.personalagent.storage.Store;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;
import java.time.*;
import java.util.*;
import java.nio.charset.StandardCharsets;
import java.util.stream.Collectors;
import static com.example.personalagent.Api.*;

@Service
public class RecordService {
    private final Store store; private final ObjectMapper json;
    public RecordService(Store store,ObjectMapper json){this.store=store;this.json=json;}
    public Store store(){return store;}
    public static String time(Object value){
        if(value==null||value.toString().trim().isEmpty())return null;
        String s=value.toString();try{return instant(Instant.parse(s));}catch(Exception ignored){}
        try{return instant(OffsetDateTime.parse(s).toInstant());}catch(Exception ignored){}
        try{return instant(LocalDateTime.parse(s).atZone(ZoneId.of("Asia/Shanghai")).toInstant());}catch(Exception ignored){}
        try{return instant(LocalDate.parse(s).atStartOfDay(ZoneId.of("Asia/Shanghai")).toInstant());}catch(Exception e){throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY,"时间格式无效");}
    }
    public Map<String,Object> get(String id){Map<String,Object> r=store.get("records",id);if(r==null)throw new ResponseStatusException(HttpStatus.NOT_FOUND,"记录不存在");return r;}
    public static long revision(Map<String,Map<String,Map<String,Object>>> all){Map<String,Object> meta=all.computeIfAbsent("meta",k->new LinkedHashMap<>()).computeIfAbsent("revision",k->map("value",0));long r=((Number)meta.get("value")).longValue()+1;meta.put("value",r);return r;}
    public synchronized Map<String,Object> create(String kind,Map<String,Object> data,String entity,String status){
        String key=text(data,"idempotency_key");if(!key.isEmpty()){Map<String,Object> saved=store.get("operations",kind+":"+key);if(saved!=null)return get(text(saved,"record_id"));}
        Map<String,Object> r=make(kind,data,entity,status);
        store.mutate(all->{all.computeIfAbsent("records",k->new LinkedHashMap<>()).put(text(r,"id"),r);markPublish(all,r);revision(all);if(!key.isEmpty())all.computeIfAbsent("operations",k->new LinkedHashMap<>()).put(kind+":"+key,map("record_id",r.get("id")));if(Boolean.TRUE.equals(r.get("important")))trigger(all,entity==null?text(r,"id"):entity,text(r,"id"),"important-record");});
        return r;
    }
    public Map<String,Object> make(String kind,Map<String,Object> data,String entity,String status){
        String title=text(data,"title").trim(),content=text(data,"content").trim();require(!title.isEmpty()&&title.length()<=200&&content.length()<=200000,"标题必填，最多200字；正文最多20万字");String at=now(),occurred=time(data.get("occurred_at"));
        Map<String,Object> payload=new LinkedHashMap<>();Object supplied=data.get("payload");if(supplied instanceof Map)payload.putAll((Map<String,Object>)supplied);
        Set<String> reserved=new HashSet<>(Arrays.asList("title","content","occurred_at","important","idempotency_key","payload","status"));data.forEach((k,v)->{if(!reserved.contains(k))payload.put(k,v);});
        return map("id",id(),"kind",kind,"title",title,"content",content,"entity_id",entity,"occurred_at",occurred,"recorded_at",at,"updated_at",at,"event_at",occurred==null?at:occurred,"event_time_basis",occurred==null?"recorded":"occurred","status",status,"revision",1,"payload",payload,"archived",false,"important",Boolean.TRUE.equals(data.get("important")),"erroneous",false);
    }
    public static void markPublish(Map<String,Map<String,Map<String,Object>>> all,Map<String,Object> r){Map<String,Object> p=all.computeIfAbsent("publish",k->new LinkedHashMap<>()).computeIfAbsent(text(r,"id"),k->map("record_id",r.get("id")));p.put("state","pending");p.put("updated_at",now());}
    public static void trigger(Map<String,Map<String,Map<String,Object>>> all,String entity,String source,String reason){String id=id();all.computeIfAbsent("triggers",k->new LinkedHashMap<>()).put(id,map("id",id,"entity_id",entity,"source_id",source,"reason",reason,"created_at",now(),"handled",false));}
    public synchronized Map<String,Object> update(String id,Map<String,Object> data){
        Map<String,Object> original=get(id);require(data.get("expected_revision") instanceof Number,"修改时需要记录版本");if(((Number)data.get("expected_revision")).intValue()!=((Number)original.get("revision")).intValue())throw conflict("记录已变化，请刷新后修改");
        Map<String,Object> next=new LinkedHashMap<>(original);
        for(String key:Arrays.asList("title","content","status","archived","important","erroneous"))if(data.containsKey(key))next.put(key,data.get(key));
        require(!text(next,"title").trim().isEmpty()&&text(next,"title").length()<=200&&text(next,"content").length()<=200000,"记录长度无效");
        Set<String> statuses=new HashSet<>(Arrays.asList("active","inbox","validating","paused","completed","ended","open","done","cancelled","unverified","inconclusive","succeeded","failed"));require(statuses.contains(text(next,"status")),"状态无效");
        if(data.containsKey("occurred_at")){String t=time(data.get("occurred_at"));next.put("occurred_at",t);next.put("event_at",t==null?next.get("recorded_at"):t);next.put("event_time_basis",t==null?"recorded":"occurred");}
        Map<String,Object> p=new LinkedHashMap<>((Map<String,Object>)original.get("payload"));if(data.get("payload") instanceof Map)p.putAll((Map<String,Object>)data.get("payload"));for(String key:Arrays.asList("hypothesis","success_criteria","smallest_test","expected_result","minimal_attempt","investment_limit","due_at","outcome","evidence","time_cost","money_cost"))if(data.containsKey(key))p.put(key,data.get(key));next.put("payload",p);next.put("revision",((Number)original.get("revision")).intValue()+1);next.put("updated_at",now());
        Map<String,Object> change=make("change",map("title","修改："+text(original,"title"),"content",original.get("content"),"payload",map("previous",original,"change_type",Boolean.TRUE.equals(data.get("erroneous"))?"correction":"update")),id,"active");
        store.mutate(all->{all.get("records").put(id,next);all.get("records").put(text(change,"id"),change);markPublish(all,next);markPublish(all,change);
            if(!Objects.equals(original.get("content"),next.get("content"))||!Objects.equals(original.get("occurred_at"),next.get("occurred_at"))){
                for(Map<String,Object> m:all.getOrDefault("memories",Collections.emptyMap()).values())if(id.equals(m.get("source_id"))){m.put("status","needs_review");m.put("revision",((Number)m.get("revision")).intValue()+1);}
                for(Map<String,Object> j:all.getOrDefault("jobs",Collections.emptyMap()).values()){Object payload=j.get("payload");if(payload instanceof Map&&id.equals(((Map)payload).get("source_id"))&&!"completed".equals(j.get("status"))){j.put("status","cancelled");j.put("error","来源已更正，请使用最新记录重新分析");}}
                for(Map<String,Object> derived:all.get("records").values()){Map<String,Object> payload=(Map<String,Object>)derived.get("payload");Object sources=payload.get("source_ids");if(sources instanceof List&&((List)sources).contains(id)){payload.put("source_corrected",true);markPublish(all,derived);}}
            }
            revision(all);});return next;
    }
    public Map<String,Object> list(String kind,String entity,String query,int limit,String cursor,boolean archived){
        Map<String,Map<String,Map<String,Object>>> snapshot=store.snapshot();Map<String,Object> meta=snapshot.getOrDefault("meta",Collections.emptyMap()).get("revision");long revision=meta==null?0:((Number)meta.get("value")).longValue();int pageSize=Math.max(1,Math.min(limit,100));String signature=Arrays.asList(kind,entity,query,archived).toString();List<String> last=null;
        if(cursor!=null&&!cursor.isEmpty())try{Map<String,Object> c=json.readValue(Base64.getUrlDecoder().decode(cursor),Map.class);if(((Number)c.get("revision")).longValue()!=revision||!signature.equals(c.get("signature")))throw conflict("历史已变化，请重新加载列表");last=(List<String>)c.get("last");}catch(ResponseStatusException e){throw e;}catch(Exception e){throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY,"分页游标无效");}
        final List<String> boundary=last;Set<String> kinds=kind==null?null:new HashSet<>(Arrays.asList(kind.split(",")));Comparator<Map<String,Object>> order=Comparator.comparing((Map<String,Object> r)->text(r,"event_at")).thenComparing(r->text(r,"recorded_at")).thenComparing(r->text(r,"id"));
        List<Map<String,Object>> values=snapshot.getOrDefault("records",Collections.emptyMap()).values().stream().filter(r->(archived||!Boolean.TRUE.equals(r.get("archived")))&&(kinds==null||kinds.contains(text(r,"kind")))&&(entity==null||entity.equals(r.get("entity_id")))&&(query==null||query.isEmpty()||(text(r,"title")+text(r,"content")).toLowerCase(Locale.ROOT).contains(query.toLowerCase(Locale.ROOT)))).filter(r->boundary==null||order.compare(r,map("event_at",boundary.get(0),"recorded_at",boundary.get(1),"id",boundary.get(2)))<0).sorted(order.reversed()).limit(pageSize+1).collect(Collectors.toList());
        String next=null;if(values.size()>pageSize){values.remove(pageSize);Map<String,Object> end=values.get(values.size()-1);try{next=Base64.getUrlEncoder().encodeToString(json.writeValueAsBytes(map("revision",revision,"signature",signature,"last",Arrays.asList(end.get("event_at"),end.get("recorded_at"),end.get("id")))));}catch(Exception e){throw new IllegalStateException("分页失败");}}return map("items",values,"next_cursor",next,"revision",revision);
    }
    public synchronized void delete(String id){
        get(id);Set<String> remove=new HashSet<>();remove.add(id);
        List<Map<String,Object>> records=store.list("records");boolean changed;
        do{changed=false;for(Map<String,Object> r:records){String rid=text(r,"id");Object p=r.get("payload");boolean linked=remove.contains(text(r,"entity_id"));if(p instanceof Map){Object sources=((Map)p).get("source_ids");if(sources instanceof List)for(Object s:(List)sources)linked|=remove.contains(String.valueOf(s));}if(linked&&remove.add(rid))changed=true;}}while(changed);
        store.mutate(all->{for(String rid:remove){all.getOrDefault("records",new LinkedHashMap<>()).remove(rid);all.computeIfAbsent("deletions",k->new LinkedHashMap<>()).put(rid,map("id",rid,"kind","source","deleted_at",now()));}for(String c:Arrays.asList("memories","sources","chunks","notifications","jobs","triggers")){Map<String,Map<String,Object>> items=all.get(c);if(items!=null)items.entrySet().removeIf(e->{Map<String,Object> value=e.getValue();boolean linked=remove.contains(text(value,"source_id"))||remove.contains(text(value,"record_id"))||remove.contains(text(value,"conversation_id"));Object payload=value.get("payload");if(payload instanceof Map){linked|=remove.contains(text((Map<String,Object>)payload,"source_id"));Object sources=((Map)payload).get("source_ids");if(sources instanceof List)for(Object s:(List)sources)linked|=remove.contains(String.valueOf(s));}return linked;});}revision(all);});
    }
}
