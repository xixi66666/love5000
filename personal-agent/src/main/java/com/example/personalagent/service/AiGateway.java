package com.example.personalagent.service;

import com.example.common.ai.*;
import com.fasterxml.jackson.databind.*;
import org.springframework.stereotype.Service;
import java.net.URI;
import java.util.*;
import static com.example.personalagent.Api.*;

/** 沿用统一模型选择；服务原配置只从根目录 model.properties 读取，不接受网页提交密钥。 */
@Service
public class AiGateway {
    private final ObjectMapper json;
    public AiGateway(ObjectMapper json){this.json=json;}
    public String complete(String system,String prompt)throws Exception {
        List<Object> messages=Arrays.asList(map("role","system","content",system),map("role","user","content",prompt));
        Map<String,Object> payload=map("messages",messages,"max_tokens",4000);
        JsonNode response=new ModelRoutingClient(json).tryChat("personal-agent",payload);
        if(response==null){
            ModelProperties.Route route=ModelProperties.load().route("personal-agent");
            if(route==null||route.provider().apiKey().isEmpty())throw new MissingModelException();
            URI endpoint=URI.create(route.provider().baseUrl()+"/chat/completions");
            require("https".equals(endpoint.getScheme())&&endpoint.getHost()!=null&&endpoint.getUserInfo()==null&&endpoint.getQuery()==null&&endpoint.getFragment()==null,"原配置模型地址必须是 HTTPS 地址");
            payload.put("model",route.modelId());
            response=new ModelHttp(json,15000,2*1024*1024).request(endpoint.toString(),route.provider().apiKey(),json.valueToTree(payload),180000);
        }
        String result=response.path("choices").path(0).path("message").path("content").asText();
        if(result.trim().isEmpty()||result.length()>60000)throw new java.io.IOException("模型没有返回有效的分析正文");
        return result;
    }
    public static class MissingModelException extends Exception {}
}
