package com.example.personalagent.service;

import com.example.personalagent.AgentConfig;
import com.example.personalagent.storage.Store;
import org.springframework.stereotype.Service;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.stream.*;
import java.util.regex.*;
import static com.example.personalagent.Api.*;

@Service
public class KnowledgeService {
    private final Store store;private final RecordService records;private final AgentConfig config;private final VaultService vault;
    public KnowledgeService(Store store,RecordService records,AgentConfig config,VaultService vault){this.store=store;this.records=records;this.config=config;this.vault=vault;}
    private List<Path> roots(String raw,String fallback){return Arrays.stream((raw.isEmpty()?fallback:raw).split(Pattern.quote(java.io.File.pathSeparator))).filter(s->!s.isEmpty()).map(s->Paths.get(s).toAbsolutePath().normalize()).collect(Collectors.toList());}
    private List<Path> skillRoots(){return roots(config.getSkillRoots(),System.getProperty("user.home")+"/.codex/skills");}
    private List<Path> bookRoots(){return roots(config.getBookRoots(),"D:/codex-book/books");}
    private Path approved(String raw,List<Path> roots)throws Exception{Path path=Paths.get(raw).toRealPath();for(Path root:roots)if(Files.exists(root)&&path.startsWith(root.toRealPath())&&!Files.isSymbolicLink(Paths.get(raw)))return path;throw new IllegalArgumentException("资料路径不在已授权目录中");}
    public List<Map<String,Object>> skills(){List<Map<String,Object>> result=new ArrayList<>();for(Path root:skillRoots())for(String name:Arrays.asList("howard-marks-cycle","naval-wisdom","nison-candlestick")){Path skill=root.resolve(name).resolve("SKILL.md");if(Files.isRegularFile(skill))result.add(map("name",name,"title",name,"skill_path",skill.toString(),"path",skill.toString(),"available",true));}return result;}
    public synchronized Map<String,Object> importBook(Map<String,Object> data)throws Exception {
        String skill=text(data,"skill_path"),file=text(data,"file_path"),title=text(data,"title");Map<String,Object> input=new LinkedHashMap<>(data);List<Path> sourceFiles=new ArrayList<>();
        if(!skill.isEmpty()){
            Path path=approved(skill,skillRoots());require(path.getFileName().toString().equals("SKILL.md"),"请选择已发现的读书 skill");title=title.isEmpty()?path.getParent().getFileName().toString():title;input.put("content",new String(Files.readAllBytes(path),StandardCharsets.UTF_8));input.put("source_path",path.toString());
            Path ref=path.getParent().resolve("references/library-map.md");if(Files.isRegularFile(ref)){String map=new String(Files.readAllBytes(ref),StandardCharsets.UTF_8);for(Path root:bookRoots())if(Files.exists(root)){try(Stream<Path> dirs=Files.list(root)){for(Path book:dirs.filter(Files::isDirectory).collect(Collectors.toList()))if(map.contains(book.getFileName().toString())){Path chapters=book.resolve("content/chapters");if(Files.isDirectory(chapters))try(Stream<Path> files=Files.walk(chapters)){sourceFiles.addAll(files.filter(p->Files.isRegularFile(p)&&p.toString().endsWith(".md")).sorted().limit(500).collect(Collectors.toList()));}Path topics=book.resolve("index/topics.zh.md");if(Files.isRegularFile(topics))sourceFiles.add(topics);}}}}
        } else if(!file.isEmpty()) {Path path=approved(file,bookRoots());require(path.toString().toLowerCase(Locale.ROOT).endsWith(".md")||path.toString().toLowerCase(Locale.ROOT).endsWith(".txt"),"第一版支持 Markdown / TXT 书源");sourceFiles.add(path);input.put("source_path",path.toString());if(title.isEmpty())title=path.getFileName().toString();}
        input.put("title",title);Map<String,Object> book=records.create("book",input,null,"active");String sourceId=text(book,"id");List<Map<String,Object>> chunks=new ArrayList<>();int position=0;long total=0;for(Path path:sourceFiles){Path source=approved(path.toString(),bookRoots());long size=Files.size(source);total+=size;require(size<=5000000&&total<=50000000,"书源过大，请分章节导入");String body=new String(Files.readAllBytes(source),StandardCharsets.UTF_8);for(int start=0;start<body.length();start+=1200){String snippet=body.substring(start,Math.min(start+1600,body.length()));chunks.add(map("id",id(),"source_id",sourceId,"record_id",sourceId,"title",title,"text",snippet,"position",position++,"path",source.toString()));}}
        store.mutate(all->{all.computeIfAbsent("sources",k->new LinkedHashMap<>()).put(sourceId,map("id",sourceId,"record_id",sourceId,"kind","book","path",text(input,"source_path"),"active",true,"updated_at",now()));Map<String,Map<String,Object>> index=all.computeIfAbsent("chunks",k->new LinkedHashMap<>());for(Map<String,Object> c:chunks)index.put(text(c,"id"),c);});vault.flush();return book;
    }
    public synchronized Map<String,Object> reindex()throws Exception {
        Set<String> present=new HashSet<>();int count=0;
        for(String directory:Arrays.asList("30-生活与见解/人工心得","20-阅读与知识/原始笔记")){Path root=vault.safe(directory);try(Stream<Path> files=Files.walk(root)){for(Path path:files.filter(p->Files.isRegularFile(p)&&p.toString().endsWith(".md")&&!Files.isSymbolicLink(p)).collect(Collectors.toList())){Path approved=vault.safe(config.vaultPath().relativize(path).toString());String relative=config.vaultPath().relativize(approved).toString();String sourceId="manual-"+VaultService.hash(relative.getBytes(StandardCharsets.UTF_8));present.add(sourceId);require(Files.size(path)<=5000000,"手工笔记超过5MB，请拆分");String content=new String(Files.readAllBytes(path),StandardCharsets.UTF_8),hash=VaultService.hash(content.getBytes(StandardCharsets.UTF_8));Map<String,Object> old=store.get("sources",sourceId);if(old!=null&&hash.equals(old.get("content_hash")))continue;
            String title=path.getFileName().toString();List<Map<String,Object>> chunks=new ArrayList<>();for(int start=0;start<content.length();start+=1200)chunks.add(map("id",id(),"source_id",sourceId,"title",title,"text",content.substring(start,Math.min(start+1600,content.length())),"path",relative,"position",start/1200));
            store.mutate(all->{all.computeIfAbsent("sources",k->new LinkedHashMap<>()).put(sourceId,map("id",sourceId,"kind","manual","path",relative,"content_hash",hash,"active",true,"updated_at",now()));Map<String,Map<String,Object>> index=all.computeIfAbsent("chunks",k->new LinkedHashMap<>());index.entrySet().removeIf(e->sourceId.equals(e.getValue().get("source_id")));for(Map<String,Object> c:chunks)index.put(text(c,"id"),c);});count++;
        }}}
        store.mutate(all->{Map<String,Map<String,Object>> sources=all.getOrDefault("sources",new LinkedHashMap<>());Set<String> removed=new HashSet<>();sources.entrySet().removeIf(e->{boolean gone="manual".equals(e.getValue().get("kind"))&&!present.contains(e.getKey());if(gone)removed.add(e.getKey());return gone;});for(String c:Arrays.asList("chunks","memories"))all.getOrDefault(c,new LinkedHashMap<>()).entrySet().removeIf(e->removed.contains(text(e.getValue(),"source_id")));});return map("updated",count,"manual_sources",present.size(),"index_type","本地关键词索引");
    }
    public List<Map<String,Object>> search(String query,int limit){require(query!=null&&!query.trim().isEmpty()&&query.length()<=300,"搜索词应为1到300字");String normalized=query.toLowerCase(Locale.ROOT).trim();List<String> terms=new ArrayList<>();terms.add(normalized);for(String term:normalized.split("\\s+"))if(term.length()>1)terms.add(term);
        if(normalized.length()>3){for(int i=0;i<normalized.length()-2;i++){String gram=normalized.substring(i,i+3);if(gram.matches("[\\p{IsHan}]{3}")&&!terms.contains(gram))terms.add(gram);}}
        String[][] aliases={{"财富","wealth"},{"幸福","happiness"},{"风险","risk"},{"周期","cycle"},{"杠杆","leverage"},{"判断","judgment"},{"蜡烛","candlestick"},{"阅读","reading"},{"具体知识","specific knowledge"}};for(String[] alias:aliases)if(normalized.contains(alias[0]))terms.add(alias[1]);
        List<Map<String,Object>> candidates=new ArrayList<>();for(Map<String,Object> r:store.list("records"))if(!Boolean.TRUE.equals(r.get("erroneous"))&&!"change".equals(r.get("kind"))&&!"message".equals(r.get("kind")))candidates.add(map("source_id",r.get("id"),"record_id",r.get("id"),"title",r.get("title"),"text",r.get("content"),"kind",r.get("kind"),"as_of",r.get("updated_at")));
        candidates.addAll(store.list("chunks"));List<Map<String,Object>> scored=new ArrayList<>();for(Map<String,Object> c:candidates){String body=text(c,"text").toLowerCase(Locale.ROOT),title=text(c,"title").toLowerCase(Locale.ROOT);int score=0;for(String term:terms){if(title.contains(term))score+=6;if(body.contains(term))score+=3;}if(score>0){Map<String,Object> found=new LinkedHashMap<>(c);found.put("score",score);String full=text(c,"text");int match=full.toLowerCase(Locale.ROOT).indexOf(normalized),start=Math.max(0,match-200);found.put("text",full.substring(start,Math.min(full.length(),start+1600)));scored.add(found);}}
        scored.sort(Comparator.comparing((Map<String,Object> r)->((Number)r.get("score")).intValue()).reversed().thenComparing(r->text(r,"source_id")));return scored.subList(0,Math.min(scored.size(),Math.max(1,Math.min(limit,20))));
    }
}
