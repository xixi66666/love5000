package com.example.personalagent.model;
import java.util.*;

/** 一个真实 Markdown 文件；revision 是原始内容的 SHA-256。 */
public class VaultNote {
    public String path,title,domain,revision,content,body,modifiedAt;
    public Map<String,Object> properties=new LinkedHashMap<>();
    public List<String> links=new ArrayList<>();
    public boolean eligibleForAi(){
        return !path.startsWith("90-模板/")&&!Boolean.TRUE.equals(properties.get("ai_exclude"))&&!"ai_generated".equals(properties.get("origin"))
            &&!Arrays.asList("archived","draft","corrected").contains(String.valueOf(properties.get("status")));
    }
}
