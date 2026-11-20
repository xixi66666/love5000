package com.example.personalagent.service;

import com.example.personalagent.AgentConfig;
import org.springframework.stereotype.Service;
import javax.annotation.PreDestroy;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import static com.example.personalagent.Api.*;

/** 真正调用 Quartz 构建；私人产物独立保存，不进入 jar、Git 或公开托管。 */
@Service
public class QuartzService {
    private final AgentConfig config;
    private final VaultService vault;
    private final WorkspaceState state;
    private final ExecutorService worker=Executors.newSingleThreadExecutor(r->{Thread t=new Thread(r,"quartz-builder");t.setDaemon(true);return t;});
    private volatile Map<String,Object> progress=map("status","idle");
    private volatile Process process;
    public QuartzService(AgentConfig config,VaultService vault,WorkspaceState state){this.config=config;this.vault=vault;this.state=state;}
    public Map<String,Object> status()throws Exception {
        Map<String,Object> result=new LinkedHashMap<>(progress),published=state.get("quartz_publication");
        result.put("installed",Files.isDirectory(config.quartzPath().resolve("node_modules")));
        result.put("ready",published!=null&&vault.fingerprint().equals(published.get("revision")));
        result.put("published_at",published==null?null:published.get("published_at"));result.put("url","/library/");return result;
    }
    public synchronized Map<String,Object> build()throws Exception {
        if("building".equals(progress.get("status")))return status();
        require(Files.isRegularFile(config.quartzPath().resolve("quartz/bootstrap-cli.mjs"))&&Files.isDirectory(config.quartzPath().resolve("node_modules")),"请先在 personal-agent/quartz 执行 npm ci");
        progress=map("status","building","started_at",now());worker.submit(this::compile);return status();
    }
    private void compile(){
        try{
            String id=id();Path directory=config.dataPath().resolve("quartz-builds").resolve(id),source=directory.resolve("source"),output=directory.resolve("site");
            Files.createDirectories(source);String revision,obsidianUrl;
            synchronized(vault){
                revision=vault.fingerprint();obsidianUrl=vault.obsidian("");Path root=vault.root();
                for(Path original:vault.files()){
                    Path relative=root.relativize(original),target=source.resolve(relative);
                    String relativePath = relative.toString().replace('\\','/');
                    if(relativePath.startsWith(HealthArchive.ORIGINALS) || relativePath.startsWith(LocalDocuments.ORIGINALS))continue;
                    Files.createDirectories(target.getParent());
                    // 只复制经过根目录/链接检查的允许文件，不包含 .obsidian 与服务配置。
                    Files.copy(vault.safe(relativePath),target,StandardCopyOption.COPY_ATTRIBUTES);
                }
                if(!revision.equals(vault.fingerprint()))throw new IllegalStateException("复制期间资料已变化，请重试");
            }
            if(!Files.exists(source.resolve("index.md")))Files.write(source.resolve("index.md"),"---\ntitle: 我的长期资料库\n---\n\n# 我的长期资料库\n\n通过左侧目录、搜索和关系图浏览你的 Obsidian 资料。\n".getBytes(StandardCharsets.UTF_8));
            ProcessBuilder builder=new ProcessBuilder(config.getNodeCommand(),"quartz/bootstrap-cli.mjs","build","--directory",source.toString(),"--output",output.toString(),"--concurrency","1");
            builder.directory(config.quartzPath().toFile()).redirectErrorStream(true).redirectOutput(directory.resolve("build.log").toFile());
            builder.environment().keySet().removeIf(k->k.toUpperCase(Locale.ROOT).matches(".*(KEY|TOKEN|PASSWORD|SECRET).*"));
            process=builder.start();
            if(!process.waitFor(180,TimeUnit.SECONDS)){process.destroyForcibly();throw new IllegalStateException("Quartz 构建超时");}
            if(process.exitValue()!=0||!Files.isRegularFile(output.resolve("index.html")))throw new IllegalStateException("Quartz 构建失败，请查看私人数据目录中的构建日志");
            try(java.util.stream.Stream<Path> pages=Files.walk(output)){
                for(Path page:pages.filter(p->p.toString().endsWith(".html")).collect(java.util.stream.Collectors.toList())){
                    String html=new String(Files.readAllBytes(page),StandardCharsets.UTF_8);
                    Files.write(page,html.replace("href=\"obsidian://open\"","href=\""+obsidianUrl+"\"").getBytes(StandardCharsets.UTF_8));
                }
            }
            synchronized(vault){
                if(!revision.equals(vault.fingerprint()))throw new IllegalStateException("资料在构建期间已变化，请重新生成");
                Map<String,Object> previous=state.get("quartz_publication");
                state.put("quartz_publication",map("id",id,"revision",revision,"published_at",now()));
                pruneBuilds(id,previous==null?"":String.valueOf(previous.get("id")));
            }
            progress=map("status","completed","finished_at",now());
        }catch(Exception e){progress=map("status","failed","message",e instanceof IllegalStateException?e.getMessage():"构建未完成，请检查 Node.js、依赖与资料格式","finished_at",now());}
        finally{process=null;}
    }
    private void pruneBuilds(String current,String previous){
        // 只清理本服务生成的 UUID 快照，保留当前和上一版；不触及 Vault 与笔记备份。
        try{
            Path base=config.dataPath().resolve("quartz-builds").toRealPath();
            if(!base.startsWith(config.dataPath().toRealPath()))return;
            try(java.util.stream.Stream<Path> directories=Files.list(base)){
                for(Path directory:directories.collect(java.util.stream.Collectors.toList())){
                    String name=directory.getFileName().toString();
                    if(name.equals(current)||name.equals(previous)||!name.matches("[0-9a-f-]{36}")||Files.isSymbolicLink(directory))continue;
                    if(!directory.toRealPath().startsWith(base))continue;
                    Files.walkFileTree(directory,new SimpleFileVisitor<Path>(){
                        @Override public FileVisitResult visitFile(Path file,java.nio.file.attribute.BasicFileAttributes attrs)throws java.io.IOException{Files.delete(file);return FileVisitResult.CONTINUE;}
                        @Override public FileVisitResult postVisitDirectory(Path dir,java.io.IOException error)throws java.io.IOException{if(error!=null)throw error;Files.delete(dir);return FileVisitResult.CONTINUE;}
                    });
                }
            }
        }catch(Exception ignored){/* 清理失败保留快照，不影响当前资料页发布。 */}
    }
    public Path resolve(String relative)throws Exception {
        Map<String,Object> publication=state.get("quartz_publication");
        if(publication==null||!vault.fingerprint().equals(publication.get("revision")))throw conflict("资料已变化，请回到工作台重新生成 Quartz 浏览页");
        Path root=config.dataPath().resolve("quartz-builds").resolve(String.valueOf(publication.get("id"))).resolve("site").toRealPath();
        require(relative!=null&&!relative.contains("\\")&&!relative.contains(":"),"页面路径无效");
        Path file=root.resolve(relative.isEmpty()?"index.html":relative).normalize();
        require(file.startsWith(root)&&!Files.isSymbolicLink(file),"页面路径越界");
        if(Files.isDirectory(file))file=file.resolve("index.html");
        if(!Files.exists(file)&&!file.toString().endsWith(".html"))file=Paths.get(file.toString()+".html");
        require(Files.isRegularFile(file)&&file.toRealPath().startsWith(root),"资料页面不存在");return file;
    }
    public boolean busy(){return "building".equals(progress.get("status"));}
    @PreDestroy public void close(){if(process!=null)process.destroyForcibly();worker.shutdownNow();}
}
