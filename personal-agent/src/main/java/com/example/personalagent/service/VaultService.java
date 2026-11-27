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
import java.net.URLEncoder;
import java.io.IOException;
import static com.example.personalagent.Api.*;

/**
 * 以文件为唯一事实源的资料库服务：路径约束、Markdown 解析、检索、编辑与初始化。
 *
 * <p>属服务层核心，几乎被所有上层组件依赖：{@link AnalysisService} 取可分析素材与指纹，
 * {@link QuartzService} 取文件清单与指纹，{@link HealthArchive} 与
 * {@link LocalDocuments} 通过 {@link #safe(String)} 与 {@link #save(Map)} 落盘，
 * {@code KnowledgeController} 把它们暴露为 HTTP 接口。</p>
 *
 * <p>不建资料数据库：每次请求都重新扫描 Vault，因此外部 Obsidian 的修改立即生效；代价是
 * 扫描成本随文件数增长，所以有 20000 文件 / 500MB 的硬上限，超限时明确报错而不是返回
 * 不完整结果。{@link #fingerprint()} 采用「笔记取内容哈希、附件取大小与修改时间」的
 * 混合策略，既能在笔记变化时失效，又不必每轮重读大文件。</p>
 *
 * <p>安全模型：{@link #safe(String)} 是唯一允许拼路径的入口，它拒绝反斜杠、冒号、
 * 隐藏目录、越界路径与符号链接；frontmatter 用 SnakeYAML 的 SafeConstructor 解析并禁用
 * 重复键与别名，避免反序列化出任意类型。所有写操作都在方法级 {@code synchronized} 内
 * 完成，并用期望 revision 做乐观锁，不静默覆盖外部修改。</p>
 */
@Service
public class VaultService {
    /** 领域 slug 到 Vault 内目录的固定映射；目录名参与路径校验，改动等同于一次数据迁移。 */
    public static final Map<String,String> DOMAINS=new LinkedHashMap<>();
    // 目录编号决定 Obsidian 侧栏顺序；analysis 目录只放 AI 派生报告，不接受直接新建笔记。
    static{DOMAINS.put("profile","10-个人档案");DOMAINS.put("finance","20-财务");DOMAINS.put("health","30-健康");
        DOMAINS.put("work","40-工作");DOMAINS.put("learning","45-学习与技能");DOMAINS.put("life","50-生活");
        DOMAINS.put("relationships","55-家庭与关系");DOMAINS.put("goals","60-目标与复盘");DOMAINS.put("home","65-居住与物品");
        DOMAINS.put("documents","70-证件与合同");DOMAINS.put("analysis","80-AI分析");}
    private final AgentConfig config;
    private final WorkspaceState state;
    /**
     * 装配配置与状态，必要时创建默认仓库。
     *
     * <p>只在「状态里还没有仓库选择」且未显式配置 {@code agent.vault-dir} 时创建默认空间；
     * 显式连接的既有仓库必须已经存在，避免误建空目录覆盖用户预期。</p>
     */
    public VaultService(AgentConfig config,WorkspaceState state)throws Exception {
        this.config=config;this.state=state;
        // 仅创建默认空间；显式连接的已有仓库必须已经存在。
        if(state.get("vault_path")==null&&config.getVaultDir().isEmpty())Files.createDirectories(config.defaultVault().resolve(".obsidian"));
    }
    /**
     * 当前生效的 Vault 根目录。
     *
     * @return 绝对规范化的真实路径
     * @throws java.io.IOException {@code toRealPath()} 失败时抛出；目录不存在或根目录本身
     *         是符号链接时由前置校验转成 422
     */
    public synchronized Path root()throws IOException {
        String selected=state.get("vault_path");Path path=selected==null?config.defaultVault():Paths.get(selected);
        require(Files.isDirectory(path),"Vault 目录不存在，请在设置中连接 Obsidian 仓库");
        require(!Files.isSymbolicLink(path),"不支持链接形式的 Vault 根目录");
        return path.toRealPath();
    }
    /**
     * 切换当前仓库。
     *
     * @param path 目标目录，必须已包含 {@code .obsidian}（即用 Obsidian 打开过的仓库）
     * @throws Exception 路径为空、缺少 {@code .obsidian} 或目录本身是符号链接时抛出；
     *         切换成功会同时清空 Quartz 发布记录，让旧快照立即失效
     */
    public synchronized void connect(String path)throws Exception {
        require(path!=null&&!path.trim().isEmpty(),"请填写 Vault 的完整路径");
        Path next=Paths.get(path).toAbsolutePath().normalize();
        require(Files.isDirectory(next.resolve(".obsidian"))&&!Files.isSymbolicLink(next),"请选择已用 Obsidian 打开的仓库（应包含 .obsidian 目录）");
        state.put("vault_path",next.toRealPath().toString());state.put("quartz_publication",null);
    }
    /**
     * 把 Vault 内相对路径解析成安全可访问的绝对路径。
     *
     * <p>逐层设防：拒绝空串、反斜杠与冒号（同时挡掉 Windows 盘符与 NTFS 备用流），
     * 归一化后必须仍在根目录之内且不等于根目录；路径每一段都不得以点开头；从目标向根
     * 回溯，任一中间节点都不能是符号链接且必须真实落在根目录内。因此本方法可以安全地
     * 接受来自 HTTP 查询串的路径。</p>
     *
     * @param relative 相对路径，使用正斜杠
     * @return 解析后的绝对路径（可能尚不存在，用于新建）
     * @throws Exception 违反上述任一约束时抛出 422
     */
    public Path safe(String relative)throws Exception {
        require(relative!=null&&!relative.isEmpty()&&!relative.contains("\\")&&!relative.contains(":"),"笔记路径无效");
        Path base=root(),path=base.resolve(relative).normalize();
        require(path.startsWith(base)&&!path.equals(base),"文件路径越界");
        for(Path piece:base.relativize(path))require(!piece.toString().startsWith("."),"不允许访问隐藏目录");
        for(Path p=path;p!=null&&!p.equals(base);p=p.getParent())
            require(!Files.isSymbolicLink(p)&&(!Files.exists(p)||p.toRealPath().startsWith(base)),"不允许链接文件或越界目录");
        return path;
    }
    /**
     * 列出可参与索引与构建的文件。
     *
     * <p>跳过隐藏目录与符号链接；默认只收笔记、Bases、画板、常见图片与音视频，体检和
     * 导入原件目录额外放行文档类后缀。累计超过 20000 个文件或 500MB 时直接抛异常，
     * 宁可报错也不返回一份「看起来完整」的部分清单。</p>
     *
     * @return 按路径字符串排序的文件列表
     * @throws java.io.IOException 超过扫描上限或遍历失败时抛出
     */
    public synchronized List<Path> files()throws Exception {
        Path base=root();List<Path> result=new ArrayList<>();long[] bytes={0};
        Files.walkFileTree(base,new SimpleFileVisitor<Path>(){
            @Override public FileVisitResult preVisitDirectory(Path dir,BasicFileAttributes attrs){
                if(!dir.equals(base)&&(dir.getFileName().toString().startsWith(".")||Files.isSymbolicLink(dir)))return FileVisitResult.SKIP_SUBTREE;
                return FileVisitResult.CONTINUE;
            }
            @Override public FileVisitResult visitFile(Path file,BasicFileAttributes attrs)throws IOException {
                String name=file.getFileName().toString().toLowerCase(Locale.ROOT);
                String relative = base.relativize(file).toString().replace('\\','/');
                boolean archived = relative.startsWith(HealthArchive.ORIGINALS) || relative.startsWith(LocalDocuments.ORIGINALS);
                if(attrs.isRegularFile()&&!Files.isSymbolicLink(file)&&!name.startsWith(".")
                    &&(name.matches(".*\\.(md|base|canvas|png|jpe?g|webp|gif|pdf|mp3|mp4|wav)$")
                    || (archived && name.matches(".*\\.(" + LocalDocuments.TYPES + ")")))){
                    bytes[0]+=attrs.size();
                    if(result.size()>=20000||bytes[0]>500L*1024*1024)throw new IOException("Vault 超过 20000 文件或 500MB 的扫描上限，请连接一个较小的专属仓库");
                    result.add(file);
                }return FileVisitResult.CONTINUE;
            }
        });
        result.sort(Comparator.comparing(Path::toString));return result;
    }
    /**
     * 解析全部笔记。
     *
     * <p>排序键优先取 frontmatter 的 {@code observed_at}（事实发生时间），缺省才用文件
     * 修改时间，因此「旧事新记」不会顶到最前面；同一时间再按路径稳定排序。</p>
     *
     * @return 按时间倒序的笔记列表
     */
    public synchronized List<VaultNote> notes()throws Exception {
        List<VaultNote> notes=new ArrayList<>();
        for(Path file:files())if(file.toString().toLowerCase(Locale.ROOT).endsWith(".md"))notes.add(read(root().relativize(file).toString().replace('\\','/')));
        notes.sort(Comparator.comparing((VaultNote n)->String.valueOf(n.properties.getOrDefault("observed_at",n.modifiedAt))).reversed().thenComparing(n->n.path));
        return notes;
    }
    /**
     * 读取单篇笔记。
     *
     * @param path Vault 内相对路径，必须以 {@code .md} 结尾
     * @return 已解析的笔记；{@code revision} 为原始字节的 SHA-256，{@code modifiedAt}
     *         取文件系统修改时间
     * @throws Exception 路径越界、文件不存在或超过 5MB 时抛出
     */
    public synchronized VaultNote read(String path)throws Exception {
        Path file=safe(path);require(path.toLowerCase(Locale.ROOT).endsWith(".md")&&Files.isRegularFile(file),"笔记不存在");
        require(Files.size(file)<=5*1024*1024,"单篇笔记不能超过5MB，请拆分后重试");
        byte[] bytes=Files.readAllBytes(file);VaultNote n=parse(path,new String(bytes,StandardCharsets.UTF_8));
        n.revision=hash(bytes);n.modifiedAt=Files.getLastModifiedTime(file).toInstant().toString();return n;
    }
    /**
     * 解析 Markdown 文本：拆 frontmatter、填充属性、推断领域、抽取双链。
     *
     * <p>只处理以分隔线开头且能在 64KB 内闭合的 frontmatter，超长或未闭合按格式错误报出，
     * 而不是把 YAML 当正文。YAML 用 SafeConstructor 并关闭重复键与别名，时间类型统一转成
     * ISO-8601 字符串，保证属性可直接序列化成 JSON。{@code body} 是 frontmatter 之后的
     * 原文（换行已归一），{@code content} 保留传入的完整文本。</p>
     *
     * @param path    笔记相对路径，用于标题兜底与领域推断
     * @param content 文件原文
     * @return 解析结果；{@code revision} 需由调用方另行填充
     * @throws IllegalArgumentException frontmatter 无法解析或不是映射时抛出
     * @throws org.springframework.web.server.ResponseStatusException frontmatter 超过
     *         64KB 或未闭合时抛出 422
     */
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
        n.links = NoteReading.targets(n.body);
        return n;
    }
    /**
     * 按目录前缀推断领域，目录不匹配时用路径关键词兜底。
     *
     * @return 已知领域 slug；完全无法判断时归入 {@code life}
     */
    private String inferDomain(String path){
        for(Map.Entry<String,String> e:DOMAINS.entrySet())if(path.startsWith(e.getValue()+"/"))return e.getKey();
        if(path.contains("财")||path.contains("finance"))return "finance";
        if(path.contains("健康")||path.contains("身体"))return "health";
        if(path.contains("工作")||path.contains("项目"))return "work";
        if(path.contains("AI分析"))return "analysis";
        return "life";
    }
    /**
     * 资料库总体摘要。
     *
     * @return 路径、名称、笔记数、各领域计数（含 0 值以保证前端图表键稳定）、AI 可用篇数、
     *         资料指纹与 Obsidian 打开链接
     */
    public synchronized Map<String,Object> summary()throws Exception {
        List<VaultNote> all=notes();Map<String,Long> domains=new LinkedHashMap<>();for(String d:DOMAINS.keySet())domains.put(d,0L);
        for(VaultNote n:all)domains.put(n.domain,domains.getOrDefault(n.domain,0L)+1);
        return map("path",root().toString(),"name",root().getFileName().toString(),"notes",all.size(),"domains",domains,
            "ai_eligible",all.stream().filter(VaultNote::eligibleForAi).count(),"revision",fingerprint(),"obsidian_url",obsidian(""));
    }
    /**
     * 计算整库指纹，用于判断快照是否过期以及切换仓库后的失效。
     *
     * <p>算法是「相对路径 + 内容或状态」的 SHA-256 累积：笔记、Bases、画板取内容，
     * 其余文件只取大小与修改时间，避免每轮都读几百兆附件。任何一篇笔记内容变化、
     * 任何一个附件被替换都会改变指纹，因此适合做发布一致性校验，不适合做密码学用途。</p>
     *
     * @return 小写十六进制摘要
     * @throws Exception 文本文件超过 5MB 或扫描失败时抛出
     */
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
    /**
     * 笔记详情：原文、渲染 HTML、出链与反链。
     *
     * <p>会为算反链把整库笔记重新解析一遍，因此比 {@link #read(String)} 重得多，只用于
     * 单篇阅读页。反链判定复用 {@link NoteLinks}，与出链保持同一套解析规则。</p>
     *
     * @param path 笔记相对路径
     * @return 含 {@code reading_html}、{@code outgoing}、{@code incoming}、
     *         {@code ai_eligible} 与 Obsidian 打开链接的详情对象
     */
    public synchronized Map<String,Object> detail(String path)throws Exception {
        VaultNote n = read(path);
        List<VaultNote> all = notes();
        NoteLinks resolver = new NoteLinks(all);
        List<Map<String,Object>> incoming = new ArrayList<>();
        List<String> backlinks = new ArrayList<>();
        for (VaultNote other : all) {
            if (!other.path.equals(n.path) && resolvedLinks(other, resolver).containsKey(n.path)) {
                incoming.add(noteLabel(other));
                backlinks.add(other.path);
            }
        }
        return map("path",n.path,"title",n.title,"domain",n.domain,"revision",n.revision,"content",n.content,"body",n.body,
            "properties",n.properties,"links",n.links,"backlinks",backlinks,"obsidian_url",obsidian(path),"ai_eligible",n.eligibleForAi(),
            "reading_html",NoteReading.render(n, resolver),"reading_truncated",NoteReading.truncated(n),"modified_at",n.modifiedAt,
            "incoming",incoming,"outgoing",new ArrayList<>(resolvedLinks(n, resolver).values()));
    }

    /**
     * 工作台总览：按领域裁剪的最近笔记、双链图与近半年编辑统计。
     *
     * <p>节点上限 48 个，边只保留两端都在节点集内的链接，避免前端渲染整库图谱；最近笔记
     * 最多 5 条。健康领域额外纳入体检解读草稿（其领域为 {@code analysis}），让「报告—解读」
     * 在同一视图里可见；模板目录一律跳过。</p>
     *
     * @param domain 领域 slug，空串表示全库
     * @return {@code recent/nodes/edges/edits/total}；{@code edits} 为最近 6 个月（含本月）
     *         的每月笔记数，顺序由旧到新
     * @throws org.springframework.web.server.ResponseStatusException 领域不存在时抛出 422
     */
    public synchronized Map<String,Object> overview(String domain) throws Exception {
        require(domain.isEmpty() || DOMAINS.containsKey(domain), "资料领域无效");
        List<VaultNote> all = notes();
        all.sort(Comparator.comparing((VaultNote note) -> note.modifiedAt).reversed().thenComparing(note -> note.path));
        NoteLinks resolver = new NoteLinks(all);
        Set<String> paths = new HashSet<>();
        List<Map<String,Object>> recent = new ArrayList<>(), nodes = new ArrayList<>(), edges = new ArrayList<>();
        Map<String,Long> edits = new LinkedHashMap<>();
        YearMonth month = YearMonth.now(ZoneId.of("Asia/Shanghai"));
        for (int age = 5; age >= 0; age--) edits.put(month.minusMonths(age).toString(), 0L);
        long count = 0;
        for (VaultNote note : all) {
            if (note.path.startsWith("90-模板/")) continue;
            boolean inDomain = domain.isEmpty() || domain.equals(note.domain);
            boolean healthDraft = "health".equals(domain) && "exam_analysis".equals(note.properties.get("record_type"));
            if (!inDomain && !healthDraft) continue;
            if (inDomain) {
                count++;
                String updated = YearMonth.from(Instant.parse(note.modifiedAt).atZone(ZoneId.of("Asia/Shanghai"))).toString();
                edits.computeIfPresent(updated, (key, value) -> value + 1);
            }
            if (recent.size() < 5) recent.add(noteLabel(note));
            if (nodes.size() < 48) {
                paths.add(note.path);
                nodes.add(noteLabel(note));
            }
        }
        for (VaultNote note : all) {
            if (!paths.contains(note.path)) continue;
            for (String target : resolvedLinks(note, resolver).keySet()) {
                if (paths.contains(target)) edges.add(map("from", note.path, "to", target));
            }
        }
        return map("recent", recent, "nodes", nodes, "edges", edges, "edits", edits, "total", count);
    }

    /**
     * 解析一篇笔记的全部出链，按目标路径去重并保持出现顺序。
     *
     * @return 目标路径到目标标签的映射；自链接与被解析器判定为歧义的链接不计入
     */
    private static Map<String,Map<String,Object>> resolvedLinks(VaultNote note, NoteLinks resolver) {
        Map<String,Map<String,Object>> targets = new LinkedHashMap<>();
        for (String link : note.links) {
            VaultNote target = resolver.resolve(note, link);
            if (target != null && !note.path.equals(target.path)) targets.putIfAbsent(target.path, noteLabel(target));
        }
        return targets;
    }

    /** 生成笔记的轻量标签，供最近列表、图谱节点与反链展示复用。 */
    private static Map<String,Object> noteLabel(VaultNote note) {
        return map("path",note.path,"title",note.title,"domain",note.domain,"modified_at",note.modifiedAt);
    }
    /**
     * 新建或覆盖一篇 Markdown 笔记，带乐观锁与编辑前备份。
     *
     * <p>{@code path} 为空时按 {@code domain} 生成 UUID 文件名，领域不接受 {@code analysis}
     * （该目录只放派生报告）。写前先解析一遍，非法 frontmatter 不落盘；覆盖既有文件时
     * 必须提供与当前内容一致的 {@code expected_revision}，否则 409，并先把旧内容备份到
     * {@code note-backups/<随机id>.md}。备份与写入之间再查一次哈希，防止期间被外部修改。</p>
     *
     * @param input {@code path}/{@code content}/{@code expected_revision}；新建时用
     *              {@code domain} 代替 path
     * @return 写入后的笔记（含新 revision）
     * @throws Exception 内容为空或超过 5MB、领域非法、路径越界、revision 不匹配时抛出；
     *         成功后清空 Quartz 发布记录，因为快照已过期
     */
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
    /**
     * 写入一份 AI 分析报告。
     *
     * <p>目标固定在 {@code 80-AI分析/} 且不允许覆盖：同一 id 的报告只写一次，重复生成由
     * 调用方换版本号，从而保留历史草稿可追溯。</p>
     *
     * @param filename 不含目录与扩展名的文件名
     * @param content  完整 Markdown（含 frontmatter）
     * @throws Exception 目标已存在或路径越界时抛出
     */
    public synchronized void saveReport(String filename,String content)throws Exception {
        Path target=safe(DOMAINS.get("analysis")+"/"+filename+".md");
        require(!Files.exists(target),"分析报告已存在");WorkspaceState.atomic(target,content.getBytes(StandardCharsets.UTF_8));state.put("quartz_publication",null);
    }
    /**
     * 初始化仓库骨架：领域目录、模板、导航 Bases、说明笔记与 {@code .obsidian}。
     *
     * <p>幂等：只创建缺失项，已存在的文件一律不动，因此可以在用户已有仓库上反复执行；
     * 生成的说明与模板都标 {@code ai_exclude: true}，不会被选作 AI 素材。末尾清空 Quartz
     * 发布记录，让旧快照随目录结构变化失效。</p>
     *
     * @throws Exception 目录创建或写盘失败时抛出
     */
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
    /**
     * 生成 {@code obsidian://} 打开链接。
     *
     * @param path 相对路径，空串表示只打开仓库
     * @return 已 URL 编码的链接；中文路径编码后可被 Obsidian 直接识别
     */
    public String obsidian(String path)throws Exception{return "obsidian://open?vault="+encode(root().getFileName().toString())+(path.isEmpty()?"":"&file="+encode(path));}
    /** UTF-8 URL 编码，并把加号换成 {@code %20}，避免被解码成空格。 */
    private static String encode(String s)throws Exception{return URLEncoder.encode(s,"UTF-8").replace("+","%20");}
    /** 计算内容的 SHA-256 十六进制摘要，是 revision 与附件校验的统一实现。 */
    public static String hash(byte[] bytes)throws Exception{return hex(MessageDigest.getInstance("SHA-256").digest(bytes));}
    /** 字节数组转小写十六进制字符串。 */
    private static String hex(byte[] bytes){StringBuilder s=new StringBuilder();for(byte b:bytes)s.append(String.format("%02x",b&255));return s.toString();}
}
