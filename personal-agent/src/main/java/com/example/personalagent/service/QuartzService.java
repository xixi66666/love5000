package com.example.personalagent.service;

import com.example.personalagent.AgentConfig;
import org.springframework.stereotype.Service;
import javax.annotation.PreDestroy;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import static com.example.personalagent.Api.*;

/**
 * 调用外部 Quartz 5.1 源码把 Vault 编译成可浏览的静态站点，并托管其产物。
 *
 * <p>属服务层，关键协作者：{@link AgentConfig}（数据目录与 Quartz 源码位置）、
 * {@link VaultService}（文件清单与资料指纹）、{@link WorkspaceState}（发布记录）。
 * 产物落在数据目录的 {@code quartz-builds/<id>/site}，输入副本在同级 {@code source}，
 * 构建日志为 {@code build.log}；全部属私人内容，不进 jar、不进 Git、不公开部署。</p>
 *
 * <p>非显然行为：构建是异步单线程的，接口立即返回，进度靠轮询 {@link #status()}；
 * 复制前后各取一次指纹，不一致就整体失败，绝不发布半个快照。体检与导入原件目录被排除
 * 在副本之外，因此私人原件不会出现在浏览页里。子进程环境变量会剔除名称含
 * KEY/TOKEN/PASSWORD/SECRET 的项，避免把凭据带给第三方构建脚本。发布记录带资料指纹，
 * {@link #resolve(String)} 在指纹变化后直接 409，保证用户看到的永远是当前资料的快照。</p>
 */
@Service
public class QuartzService {
    private final AgentConfig config;
    private final VaultService vault;
    private final WorkspaceState state;
    /** 单线程构建执行器：避免两次构建争用同一源码目录的 node_modules 与缓存。 */
    private final ExecutorService worker=Executors.newSingleThreadExecutor(r->{Thread t=new Thread(r,"quartz-builder");t.setDaemon(true);return t;});
    /** 构建进度快照，供 {@link #status()} 无锁读取；状态值为 idle/building/completed/failed。 */
    private volatile Map<String,Object> progress=map("status","idle");
    /** 当前子进程引用，仅在构建期间非空；容器关闭时需要强杀。 */
    private volatile Process process;
    public QuartzService(AgentConfig config,VaultService vault,WorkspaceState state){this.config=config;this.vault=vault;this.state=state;}
    /**
     * 汇报 Quartz 概况。
     *
     * @return 进度字段加上 {@code installed}（依赖是否已装）、{@code ready}（快照是否与
     *         当前资料指纹一致）、{@code published_at} 与固定访问路径 {@code /library/}
     */
    public Map<String,Object> status()throws Exception {
        Map<String,Object> result=new LinkedHashMap<>(progress),published=state.get("quartz_publication");
        result.put("installed",Files.isDirectory(config.quartzPath().resolve("node_modules")));
        result.put("ready",published!=null&&vault.fingerprint().equals(published.get("revision")));
        result.put("published_at",published==null?null:published.get("published_at"));result.put("url","/library/");return result;
    }
    /**
     * 触发一次异步构建。
     *
     * <p>{@code synchronized} 让「检查状态、置为 building、提交任务」成为一个原子动作，
     * 重复点击只拿到当前状态，不会排队第二次构建。</p>
     *
     * @return 构建刚启动时的状态快照
     * @throws Exception 缺少构建脚本或 {@code node_modules} 时抛出，提示先在
     *         {@code personal-agent/quartz} 执行 {@code npm ci}
     */
    public synchronized Map<String,Object> build()throws Exception {
        if("building".equals(progress.get("status")))return status();
        require(Files.isRegularFile(config.quartzPath().resolve("quartz/bootstrap-cli.mjs"))&&Files.isDirectory(config.quartzPath().resolve("node_modules")),"请先在 personal-agent/quartz 执行 npm ci");
        progress=map("status","building","started_at",now());worker.submit(this::compile);return status();
    }
    /**
     * 构建主流程：复制资料、补齐首页、调用 Node 子进程、回写 obsidian 链接、发布快照。
     *
     * <p>子进程输出重定向到构建日志而不是内存，网页只拿到成功/失败结论；超过 180 秒强杀。
     * 发布前再次比对指纹，任何一次不一致都让本次构建失败，因为「半新半旧」的站点比没有
     * 站点更危险。失败原因写进进度对象，只有 {@link IllegalStateException} 的消息会透出，
     * 其余折成通用提示以免暴露内部路径。</p>
     */
    private void compile(){
        try{
            String id=id();Path directory=config.dataPath().resolve("quartz-builds").resolve(id),source=directory.resolve("source"),output=directory.resolve("site");
            Files.createDirectories(source);String revision,obsidianUrl;
            synchronized(vault){
                revision=vault.fingerprint();obsidianUrl=vault.obsidian("");Path root=vault.root();
                for(Path original:vault.files()){
                    Path relative=root.relativize(original),target=source.resolve(relative);
                    String relativePath = relative.toString().replace('\\','/');
                    if(relativePath.startsWith(ExamPaths.ORIGINALS) || relativePath.startsWith(LocalDocuments.ORIGINALS))continue;
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
    /**
     * 清理历史构建目录，只保留当前与上一版。
     *
     * <p>三重防护：只处理名字匹配 UUID 的目录、拒绝符号链接、删除前用真实路径确认仍在
     * 构建根目录之内。任何异常都静默忽略——清理失败不影响刚发布的站点，下轮再试即可。</p>
     *
     * @param current  当前发布目录名
     * @param previous 上一版目录名；空串表示没有上一版
     */
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
    /**
     * 把浏览页请求的 URL 路径映射到快照内的真实文件。
     *
     * <p>安全约束：快照指纹必须与当前资料一致（否则 409）；相对路径不得含反斜杠或冒号；
     * 归一化后必须仍在站点根目录内且不是符号链接。目录自动补 {@code index.html}，
     * 无扩展名的路径补 {@code .html}，以贴近 Quartz 生成的链接形态。</p>
     *
     * @param relative {@code /library/} 之后的相对路径，空串表示站点首页
     * @return 站点内的可读文件
     * @throws Exception 快照过期、路径越界或文件不存在时抛出
     */
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
    /** 是否正在构建；切换仓库或触发新构建前用它拦住并发写。 */
    public boolean busy(){return "building".equals(progress.get("status"));}
    /** 容器关闭时强杀仍在运行的 Node 子进程并停止执行器，避免遗留孤儿进程。 */
    @PreDestroy public void close(){if(process!=null)process.destroyForcibly();worker.shutdownNow();}
}
