package com.example.personalagent.storage;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import java.util.*;
import java.util.function.Consumer;

/** A single local writer; JSON documents are committed through DAO + XML as one transaction. */
@Service
public class Store {
    private final DocumentDao dao;
    private final ObjectMapper json;
    private final TransactionTemplate transaction;
    private Map<String,Map<String,Map<String,Object>>> collections=new LinkedHashMap<>();
    public Store(DocumentDao dao,ObjectMapper json,PlatformTransactionManager manager) throws Exception {
        this.dao=dao;this.json=json;this.transaction=new TransactionTemplate(manager);
        for(Map<String,Object> row:dao.all()) {
            String collection=String.valueOf(row.get("collection")),id=String.valueOf(row.get("id"));
            Object body=row.get("body");
            if(body instanceof java.sql.Clob) {java.sql.Clob clob=(java.sql.Clob)body;body=clob.getSubString(1,(int)clob.length());}
            collections.computeIfAbsent(collection,k->new LinkedHashMap<>()).put(id,json.readValue(String.valueOf(body),new TypeReference<Map<String,Object>>(){}));
        }
    }
    public synchronized List<Map<String,Object>> list(String collection) {
        return new ArrayList<>(copy(collections.getOrDefault(collection,Collections.emptyMap())).values());
    }
    public synchronized Map<String,Object> get(String collection,String id) {
        Map<String,Object> item=collections.getOrDefault(collection,Collections.emptyMap()).get(id);
        return item==null?null:copy(item);
    }
    public synchronized void put(String collection,String id,Map<String,Object> value){
        Map<String,Object> safe=copy(value);
        transaction.execute(status->{try{dao.upsert(collection,id,json.writeValueAsString(safe));}catch(Exception e){throw new IllegalStateException("本地账本写入失败",e);}return null;});
        collections.computeIfAbsent(collection,k->new LinkedHashMap<>()).put(id,safe);
    }
    public synchronized void remove(String collection,String id){
        transaction.execute(status->{dao.delete(collection,id);return null;});
        if(collections.containsKey(collection))collections.get(collection).remove(id);
    }
    public synchronized void mutate(Consumer<Map<String,Map<String,Map<String,Object>>>> mutation) {
        Map<String,Map<String,Map<String,Object>>> next=copy(collections);
        mutation.accept(next);
        transaction.execute(status->{
            for(String c:collections.keySet()) for(String id:collections.get(c).keySet())
                if(!next.containsKey(c)||!next.get(c).containsKey(id))dao.delete(c,id);
            for(String c:next.keySet()) for(String id:next.get(c).keySet()) {
                Map<String,Object> old=collections.getOrDefault(c,Collections.emptyMap()).get(id),value=next.get(c).get(id);
                if(!value.equals(old))try{dao.upsert(c,id,json.writeValueAsString(value));}catch(Exception e){throw new IllegalStateException("本地账本写入失败",e);}
            }
            return null;
        });
        collections=next;
    }
    public synchronized Map<String,Map<String,Map<String,Object>>> snapshot(){return copy(collections);}
    @SuppressWarnings("unchecked") private <T> T copy(T value){return (T)json.convertValue(value,Object.class);}
}
