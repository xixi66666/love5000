package com.example.personalagent.storage;
import java.util.*;
import org.apache.ibatis.annotations.Param;
public interface DocumentDao {
    List<Map<String,Object>> all();
    void upsert(@Param("collection") String collection,@Param("id") String id,@Param("body") String body);
    void delete(@Param("collection") String collection,@Param("id") String id);
}
