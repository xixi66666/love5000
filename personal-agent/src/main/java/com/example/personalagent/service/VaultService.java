package com.example.personalagent.service;

import com.example.personalagent.AgentConfig;
import com.example.personalagent.model.VaultNote;
import org.springframework.stereotype.Service;
import org.yaml.snakeyaml.*;
import org.yaml.snakeyaml.constructor.SafeConstructor;
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.*;
import java.util.*;
import java.util.regex.*;
import java.net.URLEncoder;
import java.io.IOException;
import static com.example.personalagent.Api.*;

/** 文件即资料：不把 Markdown 导入另一套业务数据库，也不改写外部笔记。 */
@Service
public class VaultService {
    public static final Map<String,String> DOMAINS=new LinkedHashMap<>();
    static{DOMAINS.put("profile","10-个人档案");DOMAINS.put("finance","20-财务");DOMAINS.put("health","30-健康");
        DOMAINS.put("work","40-工作");DOMAINS.put("life","50-生活");DOMAINS.put("goals","60-目标与复盘");DOMAINS.put("analysis","80-AI分析");}
    private final AgentConfig config;
    private final WorkspaceState state;
    public VaultService(AgentConfig config,WorkspaceState state)throws Exception {
        this.config=config;this.state=state;
        // 仅创建默认空间；显式连接的已有仓库必须已经存在。
        if(state.get("vault_path")==null&&config.getVaultDir().isEmpty())Files.createDirectories(config.defaultVault().resolve(".obsidian"));
    }
    public synchronized Path root()throws IOException {
        String selected=state.get("vault_path");Path path=selected==null?config.defaultVault():Paths.get(selected);
        require(Files.isDirectory(path),"Vault 目录不存在，请在设置中连接 Obsidian 仓库");
        require(!Files.isSymbolicLink(path),"不支持链接形式的 Vault 根目录");
        return path.toRealPath();
    }
    public synchronized void connect(String path)throws Exception {
        require(path!=null&&!path.trim().isEmpty(),"请填写 Vault 的完整路径");
        Path next=Paths.get(path).toAbsolutePath().normalize();
        require(Files.isDirectory(next.resolve(".obsidian"))&&!Files.isSymbolicLink(next),"请选择已用 Obsidian 打开的仓库（应包含 .obsidian 目录）");
        state.put("vault_path",next.toRealPath().toString());state.put("quartz_publication",null);
    }
    public Path safe(String relative)throws Exception {
        require(relative!=null&&!relative.isEmpty()&&!relative.contains("\\")&&!relative.contains(":"),"笔记路径无效");
        Path base=root(),path=base.resolve(relative).normalize();
        require(path.startsWith(base)&&!path.equals(base),"文件路径越界");
        for(Path piece:base.relativize(path))require(!piece.toString().startsWith("."),"不允许访问隐藏目录");
        for(Path p=path;p!=null&&!p.equals(base);p=p.getParent())
            require(!Files.isSymbolicLink(p)&&(!Files.exists(p)||p.toRealPath().startsWith(base)),"不允许链接文件或越界目录");
        return path;
    }
    /** 不跟随链接或隐藏目录；容量超过限制时明确失败，避免把不完整资料当完整结果。 */
    public synchronized List<Path> files()throws Exception {
        Path base=root();List<Path> result=new ArrayList<>();long[] bytes={0};
        Files.walkFileTree(base,new SimpleFileVisitor<Path>(){
            @Override public FileVisitResult preVisitDirectory(Path dir,BasicFileAttributes attrs){
                if(!dir.equals(base)&&(dir.getFileName().toString().startsWith(".")||Files.isSymbolicLink(dir)))return FileVisitResult.SKIP_SUBTREE;
                return FileVisitResult.CONTINUE;
            }
            @Override public FileVisitResult visitFile(Path file,BasicFileAttributes attrs)throws IOException {
                String name=file.getFileName().toString().toLowerCase(Locale.ROOT);
                if(attrs.isRegularFile()&&!Files.isSymbolicLink(file)&&!name.startsWith(".")
                    &&name.matches(".*\\.(md|base|canvas|png|jpe?g|webp|gif|pdf|mp3|mp4|wav)$")){
                    bytes[0]+=attrs.size();
                    if(result.size()>=20000||bytes[0]>500L*1024*1024)throw new IOException("Vault 超过 20000 文件或 500MB 的扫描上限，请连接一个较小的专属仓库");
                    result.add(file);
                }return FileVisitResult.CONTINUE;
            }
        });
        result.sort(Comparator.comparing(Path::toString));return result;
    }
    public synchronized List<VaultNote> notes()throws Exception {
        List<VaultNote> notes=new ArrayList<>();
        for(Path file:files())if(file.toString().toLowerCase(Locale.ROOT).endsWith(".md"))notes.add(read(root().relativize(file).toString().replace('\\','/')));
        notes.sort(Comparator.comparing((VaultNote n)->String.valueOf(n.properties.getOrDefault("observed_at",n.modifiedAt))).reversed().thenComparing(n->n.path));
        return notes;
    }
    public synchronized VaultNote read(String path)throws Exception {
        Path file=safe(path);require(path.toLowerCase(Locale.ROOT).endsWith(".md")&&Files.isRegularFile(file),"笔记不存在");
        require(Files.size(file)<=5*1024*1024,"单篇笔记不能超过5MB，请拆分后重试");
        byte[] bytes=Files.readAllBytes(file);VaultNote n=parse(path,new String(bytes,StandardCharsets.UTF_8));
        n.revision=hash(bytes);n.modifiedAt=Files.getLastModifiedTime(file).toInstant().toString();return n;
    }
    @SuppressWarnings("unchecked") public VaultNote parse(String path,String content){
        VaultNote n=new VaultNote();n.path=path;n.content=content;n.body=content;
        String normalized=content.replace("\r\n","\n");
        if(normalized.startsWith("---\n")){
            int end=normalized.indexOf("\n---\n",4);
            require(end>=0&&end<65536,"Frontmatter 格式无效或超过64KB："+path);
            LoaderOptions options=new LoaderOptions();options.setAllowDuplicateKeys(false);options.setMaxAliasesForCollections(0);options.setCodePointLimit(65536);
            try{Object value=new Yaml(new SafeConstructor(options), new org.yaml.snakeyaml.representer.Representer(new DumperOptions()), new DumperOptions(), options).load(normalized.substring(4,end));
                require(value==null||value instanceof Map,"Frontmatter 应是属性对象");
                if(value!=null){for(Map.Entry<?,?> e:((Map<?,?>)value).entrySet()){
                    Object v=e.getValue();if(v instanceof Date)v=((Date)v).toInstant().toString();n.properties.put(String.valueOf(e.getKey()),v);
                }}}
            catch(org.yaml.snakeyaml.error.YAMLException e){throw new IllegalArgumentException("Frontmatter 无法解析："+path);}
            n.body=normalized.substring(end+5);
        }
        n.title=String.valueOf(n.properties.getOrDefault("title",Paths.get(path).getFileName().toString().replaceFirst("(?i)\\.md$","")));
        n.domain=String.valueOf(n.properties.getOrDefault("domain",inferDomain(path)));
        Matcher links=Pattern.compile("\\[\\[([^\\]|#]+)(?:[^\\]]*)\\]\\]").matcher(n.body);
        while(links.find())if(!n.links.contains(links.group(1)))n.links.add(links.group(1));
        return n;
    }
    private String inferDomain(String path){
        if(path.contains("财")||path.contains("finance"))return "finance";
        if(path.contains("健康")||path.contains("身体"))return "health";
        if(path.contains("工作")||path.contains("项目"))return "work";
        if(path.contains("AI分析"))return "analysis";
        for(Map.Entry<String,String> e:DOMAINS.entrySet())if(path.startsWith(e.getValue()+"/"))return e.getKey();
        return "life";
    }
    public synchronized Map<String,Object> summary()throws Exception {
        List<VaultNote> all=notes();Map<String,Long> domains=new LinkedHashMap<>();for(String d:DOMAINS.keySet())domains.put(d,0L);
        for(VaultNote n:all)domains.put(n.domain,domains.getOrDefault(n.domain,0L)+1);
        return map("path",root().toString(),"name",root().getFileName().toString(),"notes",all.size(),"domains",domains,
            "ai_eligible",all.stream().filter(VaultNote::eligibleForAi).count(),"revision",fingerprint(),"obsidian_url",obsidian(""));
    }
    public synchronized String fingerprint()throws Exception {
        MessageDigest digest=MessageDigest.getInstance("SHA-256");Path base=root();
        for(Path file:files()){
            digest.update(base.relativize(file).toString().getBytes(StandardCharsets.UTF_8));
            // 笔记和数据库视图使用内容哈希，附件使用文件状态，避免每次重复读取视频。
            if(file.toString().matches("(?i).*\\.(md|base|canvas)$")){
                require(Files.size(file)<=5*1024*1024,"文本文件超过5MB");digest.update(Files.readAllBytes(file));
            }else digest.update((Files.size(file)+":"+Files.getLastModifiedTime(file)).getBytes(StandardCharsets.UTF_8));
        }
        return hex(digest.digest());
    }
    public synchronized Map<String,Object> detail(String path)throws Exception {
        VaultNote n=read(path);List<String> backlinks=new ArrayList<>();
        String basename=Paths.get(path).getFileName().toString().replaceFirst("(?i)\\.md$","");
        for(VaultNote other:notes())if(other.links.contains(basename)||other.links.contains(path.replaceFirst("(?i)\\.md$","")))backlinks.add(other.path);
        return map("path",n.path,"title",n.title,"domain",n.domain,"revision",n.revision,"content",n.content,"body",n.body,
            "properties",n.properties,"links",n.links,"backlinks",backlinks,"obsidian_url",obsidian(path));
    }
    public synchronized VaultNote save(Map<String,Object> input)throws Exception {
        String path=text(input,"path"),content=text(input,"content"),expected=text(input,"expected_revision");
        require(!content.trim().isEmpty()&&content.getBytes(StandardCharsets.UTF_8).length<=5*1024*1024,"笔记不能为空，且不能超过5MB");
        if(path.isEmpty()){
            String domain=text(input,"domain");require(DOMAINS.containsKey(domain)&&!domain.equals("analysis"),"资料领域无效");
            path=DOMAINS.get(domain)+"/"+id()+".md";
        }
        require(path.endsWith(".md"),"仅可保存 Markdown 笔记");parse(path,content);Path file=safe(path);
        if(Files.exists(file)){
            byte[] previous=Files.readAllBytes(file);
            if(!hash(previous).equals(expected))throw conflict("笔记已在 Obsidian 或其他页面修改，请重新加载后合并");
            WorkspaceState.atomic(config.dataPath().resolve("note-backups").resolve(id()+".md"),previous);
            if(!hash(Files.readAllBytes(file)).equals(expected))throw conflict("笔记刚刚变化，请重新加载");
        }else require(expected.isEmpty(),"原笔记已被删除或移动，请重新加载");
        WorkspaceState.atomic(file,content.getBytes(StandardCharsets.UTF_8));state.put("quartz_publication",null);return read(path);
    }
    public synchronized void saveReport(String filename,String content)throws Exception {
        Path target=safe(DOMAINS.get("analysis")+"/"+filename+".md");
        require(!Files.exists(target),"分析报告已存在");WorkspaceState.atomic(target,content.getBytes(StandardCharsets.UTF_8));state.put("quartz_publication",null);
    }
    public synchronized void initialize()throws Exception {
        for(String folder:DOMAINS.values())Files.createDirectories(root().resolve(folder));
        Files.createDirectories(root().resolve("90-模板"));Files.createDirectories(root().resolve("99-附件"));Files.createDirectories(root().resolve(".obsidian"));
        Path home=root().resolve("index.md");
        if(!Files.exists(home))WorkspaceState.atomic(home,("---\ntitle: 我的长期资料库\ndomain: profile\nai_exclude: true\n---\n\n# 我的长期资料库\n\n资料由 Obsidian 组织，Quartz 用于浏览，AI 分析保留来源与时间。\n\n"
            +"- [[20-财务/财务资料说明|财务]]\n- [[30-健康/健康资料说明|健康]]\n- [[40-工作/工作资料说明|工作]]\n\n先记录真实信息，再进行分析。未知信息保持空白，不把建议当作事实。\n").getBytes(StandardCharsets.UTF_8));
        for(String domain:Arrays.asList("finance","health","work")){
            String folder=DOMAINS.get(domain),label=folder.substring(3);Path help=root().resolve(folder).resolve(label+"资料说明.md");
            if(!Files.exists(help))WorkspaceState.atomic(help,("---\ntitle: "+label+"资料说明\ndomain: "+domain+"\nai_exclude: true\n---\n\n# "+label+"资料\n\n这里保存你的真实记录。每条记录写清发生时间、数据来源、状态及计量单位。\n\n"
                +(domain.equals("finance")?"金额使用十进制字符串并注明币种与截至日期；资产快照不能重复累加。":domain.equals("health")?"体检指标保留单位和参考范围，记录就诊日期；AI 不能替代医生诊断。":"保存岗位、项目、反馈与成果，区分事实、他人评价和个人计划。")+"\n").getBytes(StandardCharsets.UTF_8));
        }
        Path template=root().resolve("90-模板/资料记录.md");
        if(!Files.exists(template))WorkspaceState.atomic(template,("---\ntitle: 待填写\ndomain: life\nrecord_type: observation\nobserved_at: \nrecorded_at: \nstatus: current\nsource: 本人记录\nai_exclude: false\ntags: []\n---\n\n# 事实与证据\n\n# 背景与计量单位\n\n# 待核实\n").getBytes(StandardCharsets.UTF_8));
        Files.createDirectories(root().resolve("00-导航"));
        Path base=root().resolve("00-导航/个人资料.base");
        if(!Files.exists(base))WorkspaceState.atomic(base,("filters:\n  and:\n    - 'file.ext == \"md\"'\n    - '!file.inFolder(\"90-模板\")'\nformulas:\n  note: 'link(file.path, if(title, title, file.name))'\nproperties:\n  formula.note:\n    displayName: 资料\nviews:\n"
            +"  - type: table\n    name: 全部资料\n    order: [formula.note, domain, observed_at, status, source]\n    sort:\n      - property: observed_at\n        direction: DESC\n"
            +"  - type: cards\n    name: 资料卡片\n    order: [formula.note, domain, observed_at]\n"
            +"  - type: table\n    name: 财务\n    filters: 'domain == \"finance\"'\n    order: [formula.note, observed_at, status, source]\n"
            +"  - type: table\n    name: 健康\n    filters: 'domain == \"health\"'\n    order: [formula.note, observed_at, status, source]\n"
            +"  - type: table\n    name: 工作\n    filters: 'domain == \"work\"'\n    order: [formula.note, observed_at, status, source]\n").getBytes(StandardCharsets.UTF_8));
        state.put("quartz_publication",null);
    }
    public String obsidian(String path)throws Exception{return "obsidian://open?vault="+encode(root().getFileName().toString())+(path.isEmpty()?"":"&file="+encode(path));}
    private static String encode(String s)throws Exception{return URLEncoder.encode(s,"UTF-8").replace("+","%20");}
    public static String hash(byte[] bytes)throws Exception{return hex(MessageDigest.getInstance("SHA-256").digest(bytes));}
    private static String hex(byte[] bytes){StringBuilder s=new StringBuilder();for(byte b:bytes)s.append(String.format("%02x",b&255));return s.toString();}
}
