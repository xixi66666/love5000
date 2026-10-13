package com.example.personalagent;
import java.util.*;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;
public final class Api {
    private Api(){}
    public static Map<String,Object> map(Object... pairs){Map<String,Object> m=new LinkedHashMap<>();for(int i=0;i<pairs.length;i+=2)m.put(String.valueOf(pairs[i]),pairs[i+1]);return m;}
    public static Map<String,Object> ok(Object data){return map("success",true,"data",data);}
    public static String text(Map<String,Object> m,String key){return m.get(key)==null?"":String.valueOf(m.get(key));}
    public static void require(boolean condition,String message){if(!condition)throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY,message);}
    public static ResponseStatusException conflict(String message){return new ResponseStatusException(HttpStatus.CONFLICT,message);}
    public static String id(){return UUID.randomUUID().toString();}
    public static String instant(java.time.Instant value){return new java.time.format.DateTimeFormatterBuilder().appendInstant(9).toFormatter().format(value);}
    public static String now(){return instant(java.time.Instant.now());}
}
