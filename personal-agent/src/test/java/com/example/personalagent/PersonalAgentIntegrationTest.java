package com.example.personalagent;

import com.example.personalagent.service.*;
import com.example.personalagent.storage.*;
import com.fasterxml.jackson.databind.*;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.mock.mockito.SpyBean;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.test.web.servlet.*;
import org.springframework.mock.web.MockHttpSession;
import org.springframework.transaction.PlatformTransactionManager;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import static com.example.personalagent.Api.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest(properties={"agent.background=false","logging.level.root=WARN"})
@AutoConfigureMockMvc
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class PersonalAgentIntegrationTest {
    static final Path data=Paths.get("target","test-agent-"+UUID.randomUUID()).toAbsolutePath();
    @DynamicPropertySource static void properties(DynamicPropertyRegistry r){r.add("agent.data-dir",()->data.toString());}
    @Autowired MockMvc mvc;@Autowired ObjectMapper json;@Autowired RecordService records;@Autowired VaultService vault;@Autowired KnowledgeService knowledge;@Autowired Store store;@Autowired DocumentDao dao;@Autowired PlatformTransactionManager manager;@SpyBean AgentService agent;
    static MockHttpSession session;static String csrf;
    private JsonNode body(MvcResult result)throws Exception{return json.readTree(result.getResponse().getContentAsString()).path("data");}
    @Test @Order(0) void allowsHomepageEntryNavigationAcrossLocalHosts()throws Exception {
        for(String path:Arrays.asList("/","/index.html")) {
            mvc.perform(get(path).header("Sec-Fetch-Site","cross-site").header("Sec-Fetch-Mode","navigate").header("Sec-Fetch-Dest","document")
                    .with(req->{req.setServerName("127.0.0.1");req.setServerPort(5178);return req;})).andExpect(status().isOk());
        }
    }
    @Test @Order(0) void crossSiteNavigationDoesNotPermitApisOrEmbeddedPages()throws Exception {
        mvc.perform(get("/api/auth/status").header("Sec-Fetch-Site","cross-site").header("Sec-Fetch-Mode","navigate").header("Sec-Fetch-Dest","document")).andExpect(status().isForbidden());
        mvc.perform(post("/api/auth/setup").header("Sec-Fetch-Site","cross-site").header("Sec-Fetch-Mode","navigate").header("Sec-Fetch-Dest","document").contentType("application/json").content("{}")).andExpect(status().isForbidden());
        mvc.perform(get("/").header("Sec-Fetch-Site","cross-site").header("Sec-Fetch-Mode","cors").header("Sec-Fetch-Dest","empty")).andExpect(status().isForbidden());
        mvc.perform(get("/").header("Sec-Fetch-Site","cross-site").header("Sec-Fetch-Mode","navigate").header("Sec-Fetch-Dest","iframe")).andExpect(status().isForbidden());
        mvc.perform(get("/app.js").header("Sec-Fetch-Site","cross-site").header("Sec-Fetch-Mode","navigate").header("Sec-Fetch-Dest","document")).andExpect(status().isForbidden());
        mvc.perform(get("/").header("Sec-Fetch-Site","cross-site").header("Sec-Fetch-Mode","navigate").header("Sec-Fetch-Dest","document").header("Origin","http://localhost:8080")).andExpect(status().isForbidden());
        mvc.perform(get("/").header("Sec-Fetch-Site","cross-site").header("Sec-Fetch-Mode","navigate").header("Sec-Fetch-Dest","document")
                .with(req->{req.setRemoteAddr("10.0.0.2");return req;})).andExpect(status().isForbidden());
        mvc.perform(get("/api/health").header("Sec-Fetch-Site","cross-site")).andExpect(status().isOk()).andExpect(jsonPath("$.service").value("personal-agent"));
    }
    @Test @Order(1) void localAuthenticationAndOriginGuards()throws Exception {
        mvc.perform(get("/api/health")).andExpect(status().isOk()).andExpect(jsonPath("$.success").value(true)).andExpect(jsonPath("$.service").value("personal-agent"));
        mvc.perform(get("/api/settings")).andExpect(status().isUnauthorized());
        mvc.perform(get("/api/health").with(req->{req.setRemoteAddr("10.0.0.2");return req;})).andExpect(status().isForbidden());
        mvc.perform(post("/api/auth/setup").header("Origin","https://example.invalid").contentType("application/json").content("{\"password\":\"TEST_PASSWORD_ONLY\"}")).andExpect(status().isForbidden());
        MvcResult setup=mvc.perform(post("/api/auth/setup").contentType("application/json").content("{\"password\":\"TEST_PASSWORD_ONLY\"}")).andExpect(status().isOk()).andReturn();session=(MockHttpSession)setup.getRequest().getSession();csrf=body(setup).path("csrf_token").asText();
        mvc.perform(post("/api/ideas").session(session).contentType("application/json").content("{\"title\":\"未校验\"}")).andExpect(status().isForbidden());
        mvc.perform(post("/api/auth/setup").contentType("application/json").content("{\"password\":\"TEST_PASSWORD_ONLY\"}")).andExpect(status().isConflict());
    }
    @Test @Order(2) void ideaRequiresSelectionAndEvidence()throws Exception {
        JsonNode idea=body(mvc.perform(post("/api/ideas").session(session).header("X-CSRF-Token",csrf).contentType("application/json").content("{\"title\":\"测试想法\",\"content\":\"先试一小步\"}")).andExpect(status().isOk()).andReturn());String id=idea.path("id").asText();
        mvc.perform(post("/api/ideas/"+id+"/actions").session(session).header("X-CSRF-Token",csrf).contentType("application/json").content("{\"title\":\"行动\"}")).andExpect(status().isUnprocessableEntity());
        mvc.perform(post("/api/ideas/"+id+"/activate").session(session).header("X-CSRF-Token",csrf).contentType("application/json").content("{}")).andExpect(status().isOk());
        mvc.perform(post("/api/ideas/"+id+"/events").session(session).header("X-CSRF-Token",csrf).contentType("application/json").content("{\"event_type\":\"result\",\"outcome\":\"succeeded\",\"content\":\"我觉得成功\"}")).andExpect(status().isUnprocessableEntity());
        JsonNode result=body(mvc.perform(post("/api/ideas/"+id+"/events").session(session).header("X-CSRF-Token",csrf).contentType("application/json").content("{\"event_type\":\"result\",\"content\":\"还没有数据\"}")).andExpect(status().isOk()).andReturn());assertEquals("unverified",result.path("payload").path("outcome").asText());assertTrue(Files.exists(data.resolve("vault/40-想法与行动/想法/"+id+".md")));
    }
    @Test @Order(3) void staleEditsAndVaultManualChangesAreProtected()throws Exception {
        Map<String,Object> note=records.create("life",map("title","补录旧事","content","原文","occurred_at","2020-02-03"),null,"active");String id=text(note,"id");vault.flush();Map<String,Object> p=store.get("publish",id);Path file=vault.safe(text(p,"path"));java.time.ZonedDateTime recorded=java.time.Instant.parse(text(note,"recorded_at")).atZone(java.time.ZoneId.of("Asia/Shanghai"));assertTrue(text(p,"path").contains(recorded.getYear()+"/"+String.format("%02d",recorded.getMonthValue())));assertTrue(text(note,"event_at").startsWith("2020-02-02"));Files.write(file,"Obsidian 手工修改".getBytes(StandardCharsets.UTF_8));records.update(id,map("content","网页更正","expected_revision",1));vault.flush();assertEquals("conflict",store.get("publish",id).get("state"));assertEquals("Obsidian 手工修改",new String(Files.readAllBytes(file),StandardCharsets.UTF_8));assertThrows(org.springframework.web.server.ResponseStatusException.class,()->records.update(id,map("content","旧版本","expected_revision",1)));vault.resolve(id,true);assertEquals("published",store.get("publish",id).get("state"));try(java.util.stream.Stream<Path> files=Files.list(data.resolve("vault/30-生活与见解/人工心得"))){assertTrue(files.findAny().isPresent());}
    }
    @Test @Order(4) void explicitMemoryHasSourceAndDeletionExclusion()throws Exception {
        Map<String,Object> note=records.create("insight",map("title","测试观点","content","我偏好先做小规模实验"),null,"active");String source=text(note,"id");Map<String,Object> j=agent.job("memory",map("content",note.get("content"),"source_id",source),"memory-test");doReturn(true).when(agent).configured();doReturn(json.readTree("{\"answer\":\"记录已整理\",\"memories\":[{\"content\":\"偏好小规模实验\",\"kind\":\"preference\",\"fact_key\":\"experiment-preference\",\"explicit_quote\":\"我偏好先做小规模实验\"},{\"content\":\"喜欢高风险投资\",\"kind\":\"preference\",\"fact_key\":\"risk\",\"explicit_quote\":\"并不存在\"}]}" )).when(agent).complete(anyList());ReflectionTestUtils.invokeMethod(agent,"process",j);List<Map<String,Object>> memories=store.list("memories");assertEquals(1,memories.size());assertEquals(source,memories.get(0).get("source_id"));String mid=text(memories.get(0),"id");agent.deleteMemory(mid);Map<String,Object> j2=agent.job("memory",map("content",note.get("content"),"source_id",source),"memory-test-2");ReflectionTestUtils.invokeMethod(agent,"process",j2);assertEquals(0,store.list("memories").size());reset(agent);
    }
    @Test @Order(5) void noModelRetainsChatAndWaitsForConfiguration()throws Exception {
        doReturn(false).when(agent).configured();Map<String,Object> posted=agent.chat(map("content","测试问题","idempotency_key","chat-once"));assertEquals(posted,agent.chat(map("content","测试问题","idempotency_key","chat-once")));Map<String,Object> j=store.get("jobs",text(posted,"job_id"));ReflectionTestUtils.invokeMethod(agent,"process",j);assertEquals("waiting_configuration",agent.getJob(text(posted,"job_id")).get("status"));assertEquals(1,((List)records.list("message",text(posted,"conversation_id"),null,50,null,true).get("items")).size());reset(agent);
    }
    @Test @Order(6) void manualNoteSearchSupportsShortChineseAndSourceRemoval()throws Exception {
        Path file=data.resolve("vault/30-生活与见解/人工心得/测试心得.md");Files.write(file,"星河：我的长期生活见解".getBytes(StandardCharsets.UTF_8));knowledge.reindex();assertFalse(knowledge.search("星河",10).isEmpty());Files.delete(file);knowledge.reindex();assertTrue(knowledge.search("星河",10).isEmpty());
    }
    @Test @Order(7) void sourceDeleteRemovesRevisionAndDerivativeCopies()throws Exception {
        Map<String,Object> r=records.create("insight",map("title","待删除来源","content","测试隐私内容"),null,"active");String source=text(r,"id");records.update(source,map("content","纠正后的测试隐私","expected_revision",1));Map<String,Object> review=records.create("review",map("title","衍生报告","content","测试隐私内容","source_ids",Arrays.asList(source)),null,"active");vault.flush();records.delete(source);vault.flush();assertNull(store.get("records",source));assertNull(store.get("records",text(review,"id")));assertFalse(store.list("records").stream().anyMatch(record->text(record,"content").contains("测试隐私")));assertNotNull(store.get("deletions",source));
    }
    @Test @Order(8) void persistentDataAndBackupsSurviveRestart()throws Exception {
        Store reopened=new Store(dao,json,manager);assertEquals(store.list("records").size(),reopened.list("records").size());JsonNode result=body(mvc.perform(post("/api/data/backup").session(session).header("X-CSRF-Token",csrf).contentType("application/json").content("{}")).andExpect(status().isOk()).andReturn());assertTrue(Files.isRegularFile(Paths.get(result.path("path").asText())));
    }
    @Test @Order(9) void tenThousandHistoryRecordsPageWithoutDuplicatesAndInvalidateOnChange()throws Exception {
        Map<String,Map<String,Object>> fixtures=new LinkedHashMap<>();for(int i=0;i<10000;i++){Map<String,Object> r=records.make("life",map("title","历史样本"+i,"content","样本","occurred_at",String.format("%04d-03-01",2016+i%10)),null,"active");fixtures.put(text(r,"id"),r);}store.mutate(all->{all.computeIfAbsent("records",k->new LinkedHashMap<>()).putAll(fixtures);RecordService.revision(all);});Set<String> ids=new HashSet<>();String cursor=null;int pages=0;do{Map<String,Object> result=records.list("life",null,"历史样本",100,cursor,false);for(Map<String,Object> r:(List<Map<String,Object>>)result.get("items"))assertTrue(ids.add(text(r,"id")));cursor=(String)result.get("next_cursor");pages++;}while(cursor!=null);assertEquals(10000,ids.size());assertEquals(100,pages);Map<String,Object> first=records.list("life",null,"历史样本",50,null,false);records.create("life",map("title","最新记录","content","测试"),null,"active");assertThrows(org.springframework.web.server.ResponseStatusException.class,()->records.list("life",null,"历史样本",50,(String)first.get("next_cursor"),false));
    }
    @Test @Order(10) void correctedSourceSuspendsOldMemoryAndQueuedAnalysis(){
        Map<String,Object> source=records.create("insight",map("title","更正来源测试","content","旧事实"),null,"active");String sid=text(source,"id"),mid=id();store.put("memories",mid,map("id",mid,"source_id",sid,"content","旧事实","fact_key","test-correction","kind","fact","status","active","revision",1,"valid_from",source.get("event_at")));
        Map<String,Object> job=agent.job("memory",map("source_id",sid,"content","旧事实"),"old-analysis-test");records.update(sid,map("content","正确的新事实","expected_revision",1));assertEquals("needs_review",store.get("memories",mid).get("status"));assertEquals("cancelled",agent.getJob(text(job,"id")).get("status"));
    }
    @Test @Order(11) void restoringOlderBackupPreservesDeletionTombstones()throws Exception {
        Map<String,Object> source=records.create("life",map("title","恢复删除测试","content","应被删除的测试原文"),null,"active");String sourceId=text(source,"id");vault.flush();JsonNode archive=body(mvc.perform(post("/api/data/backup").session(session).header("X-CSRF-Token",csrf).contentType("application/json").content("{}")).andExpect(status().isOk()).andReturn());Map<String,Object> publication=store.get("publish",sourceId);records.delete(sourceId);vault.flush();
        mvc.perform(post("/api/data/restore").session(session).header("X-CSRF-Token",csrf).contentType("application/json").content(json.writeValueAsString(map("filename",archive.path("filename").asText())))).andExpect(status().isOk()).andExpect(jsonPath("$.data.restored").value(true));assertNull(store.get("records",sourceId));assertFalse(Files.exists(vault.safe(text(publication,"path"))));assertNotNull(store.get("deletions",sourceId));
        mvc.perform(post("/api/data/restore").session(session).header("X-CSRF-Token",csrf).contentType("application/json").content("{\"filename\":\"../outside.zip\"}")).andExpect(status().isUnprocessableEntity());
    }
}
