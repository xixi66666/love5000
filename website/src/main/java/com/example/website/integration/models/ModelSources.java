package com.example.website.integration.models;

import com.example.common.ai.ModelProperties;
import org.springframework.core.env.Environment;

import java.net.URI;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;

/**
 * 只从项目根目录 model.properties 读取模型提供商；密钥只留在内存，不进入目录响应或选择持久化文件。
 */
public class ModelSources {
    public static class Source {
        final String id, label, base, key;
        final List<String> configured;
        Source(String id, String label, String base, String key, String models) {
            this.id=id; this.label=label; this.base=base.replaceAll("/+$", ""); this.key=key;
            List<String> names=new ArrayList<String>();
            if(models!=null) for(String name:models.split(",")) if(!name.trim().isEmpty()) names.add(name.trim());
            this.configured=names;
        }
        boolean acceptsModel(String model) {
            return configured.isEmpty() || configured.contains(model);
        }
    }
    private final Environment env;
    private final Path root;
    public ModelSources(Environment env, Path root) { this.env=env; this.root=root; }
    public static Path projectRoot() {
        Path p=Paths.get("").toAbsolutePath();
        while (p != null) { if (Files.isDirectory(p.resolve("website/python-a"))) return p; p=p.getParent(); }
        return Paths.get("").toAbsolutePath();
    }
    public Path modelFile() {
        return ModelProperties.locate(root == null ? projectRoot() : root);
    }
    public List<Source> read() {
        ModelProperties settings;
        try {
            settings = ModelProperties.load(modelFile());
        } catch (RuntimeException e) {
            // 配置缺失或无法读取时保持空目录，页面显示未就绪而不是启动失败。
            return new ArrayList<Source>();
        }
        List<Source> sources=new ArrayList<Source>();
        for (ModelProperties.Provider provider:settings.textProviders()) {
            if (provider.baseUrl().isEmpty()) continue;
            sources.add(new Source(provider.id(), provider.label(), provider.baseUrl(), provider.apiKey(),
                    String.join(",", provider.models())));
        }
        // 上游地址只能来自管理员已写好的本地配置，且远端必须 HTTPS。
        sources.removeIf(s->{try {URI u=URI.create(s.base); return u.getUserInfo()!=null || u.getQuery()!=null || u.getFragment()!=null
                || u.getHost()==null || !("https".equals(u.getScheme()) || ("strata".equals(s.id) && "http".equals(u.getScheme()))); }
            catch(Exception e){return true;}});
        return sources;
    }
    public Path strataHome(){return Paths.get(env.getProperty("website.local-services.strata-dir",env.getProperty("STRATA_HOME","F:/model/Strata")));}
}
