package com.example.website.integration.models;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.core.env.Environment;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.net.URI;
import java.util.*;

/** 只引用已有私有配置。密钥只驻留内存，不进入目录响应或选择持久化文件。 */
public class ModelSources {
    public static class Source {
        final String id, label, base, key;
        final List<String> configured;
        Source(String id, String label, String base, String key, String models) {
            this.id=id; this.label=label; this.base=base.replaceAll("/+$", ""); this.key=key;
            this.configured=Arrays.asList(models.split(","));
        }
    }
    private final Environment env;
    private final ObjectMapper json;
    private final Path root;
    public ModelSources(Environment env, ObjectMapper json, Path root) { this.env=env; this.json=json; this.root=root; }
    public static Path projectRoot() {
        Path p=Paths.get("").toAbsolutePath();
        while (p != null) { if (Files.isDirectory(p.resolve("website/python-a"))) return p; p=p.getParent(); }
        return Paths.get("").toAbsolutePath();
    }
    private String value(Map<String,String> local, String name, String fallback) {
        return env.getProperty(name, local.getOrDefault(name, fallback)).trim();
    }
    private Map<String,String> dotenv(Path path) {
        Map<String,String> values=new HashMap<>();
        try { for (String line:Files.readAllLines(path, StandardCharsets.UTF_8)) {
            String l=line.trim(); if (l.startsWith("#") || !l.contains("=")) continue;
            String[] pair=l.split("=", 2); String v=pair[1].trim();
            if (v.length()>1 && ((v.startsWith("\"") && v.endsWith("\"")) || (v.startsWith("'") && v.endsWith("'")))) v=v.substring(1,v.length()-1);
            values.put(pair[0].replace("\uFEFF", "").trim(),v);
        }} catch (Exception ignored) { /* 未配置的来源保留为不可用 */ }
        return values;
    }
    private String keyFile(String raw) {
        if (raw.isEmpty()) return "";
        try {
            Path p=Paths.get(raw); if (!p.isAbsolute()) p=root.resolve("website/skill-finder/backend").resolve(p);
            String text=new String(Files.readAllBytes(p),StandardCharsets.UTF_8).replace("\uFEFF", "").trim();
            if (!text.startsWith("{")) return text;
            JsonNode data=json.readTree(text);
            for (String name:Arrays.asList("INTRO_API_KEY","DEEPSEEK_API_KEY","intro_api_key","deepseek_api_key","api_key"))
                if (!data.path(name).asText().trim().isEmpty()) return data.path(name).asText().trim();
        } catch (Exception ignored) { }
        return "";
    }
    public List<Source> read() {
        Map<String,String> python=new HashMap<>();
        try { JsonNode data=json.readTree(root.resolve("website/python-a/deepseek.local.json").toFile());
            data.fields().forEachRemaining(e->python.put(e.getKey().toUpperCase(Locale.ROOT),e.getValue().asText()));
        } catch(Exception ignored) { }
        Map<String,String> intro=dotenv(root.resolve("website/skill-finder/backend/.env"));
        List<Source> sources=new ArrayList<>();
        sources.add(new Source("deepseek","DeepSeek",value(python,"DEEPSEEK_API_BASE","https://api.deepseek.com"),
                value(python,"DEEPSEEK_API_KEY",""),value(python,"DEEPSEEK_MODEL","deepseek-flash,deepseek-v4-pro")));
        String introKey=keyFile(value(intro,"INTRO_API_KEY_FILE",""));
        if(introKey.isEmpty()) introKey=value(intro,"INTRO_API_KEY","");
        String introBase=value(intro,"INTRO_API_BASE","https://opencode.ai/zen/go/v1");
        if(introKey.isEmpty() && introBase.startsWith("https://opencode.ai/")) {
            introKey=value(intro,"OPENCODE_API_KEY","");
            if(introKey.isEmpty()) try { introKey=json.readTree(Paths.get(System.getProperty("user.home"),".local/share/opencode/auth.json").toFile()).path("opencode-go").path("key").asText(); } catch(Exception ignored) { }
        }
        sources.add(new Source("intro","Skill Finder 网关",introBase,introKey,
                value(intro,"INTRO_MODEL","ox-alpha-free,deepseek-v4-flash").replace("opencode-go/","")));
        sources.add(new Source("openai","OpenAI 兼容接口",env.getProperty("OPENAI_BASE_URL","https://api.openai.com/v1"),
                env.getProperty("OPENAI_API_KEY",""),env.getProperty("OPENAI_CHAT_MODEL","")));
        sources.add(new Source("personal","个人 Agent 网关",env.getProperty("PERSONAL_AGENT_API_BASE","https://api.deepseek.com"),
                env.getProperty("PERSONAL_AGENT_API_KEY",""),env.getProperty("PERSONAL_AGENT_MODEL","deepseek-flash")));
        sources.add(new Source("strata","本机 Qwen · Strata","http://127.0.0.1:"+env.getProperty("website.local-services.strata-port","9999")+"/v1","",""));
        // 上游地址只能来自管理员已有配置，且远程必须 HTTPS。
        sources.removeIf(s->{try {URI u=URI.create(s.base); return u.getUserInfo()!=null || u.getQuery()!=null || u.getFragment()!=null
                || u.getHost()==null || !("https".equals(u.getScheme()) || ("strata".equals(s.id) && "http".equals(u.getScheme()))); }catch(Exception e){return true;}});
        return sources;
    }
    public Path strataHome(){return Paths.get(env.getProperty("website.local-services.strata-dir",env.getProperty("STRATA_HOME","F:/model/Strata")));}
}
