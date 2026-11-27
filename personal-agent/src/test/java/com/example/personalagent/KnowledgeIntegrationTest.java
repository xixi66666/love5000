package com.example.personalagent;

import com.example.personalagent.model.VaultNote;
import com.example.personalagent.service.*;
import com.fasterxml.jackson.databind.*;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.*;
import org.springframework.mock.web.MockHttpSession;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import static com.example.personalagent.Api.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.mockito.AdditionalMatchers.aryEq;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest(properties="logging.level.root=WARN")
@AutoConfigureMockMvc
class KnowledgeIntegrationTest {
    static final Path DATA=Paths.get("target","test-knowledge-"+UUID.randomUUID()).toAbsolutePath();
    @DynamicPropertySource static void properties(DynamicPropertyRegistry r){
        r.add("agent.data-dir",()->DATA.toString());
        // 测试必须显式隔离 Vault，不能创建或使用 D 盘的真实个人资料库。
        r.add("agent.vault-dir",()->DATA.resolve("default-vault").toString());
    }
    @Autowired MockMvc mvc;@Autowired ObjectMapper json;@Autowired VaultService vault;@Autowired WorkspaceState state;
    @Autowired AnalysisService analyses;@Autowired QuartzService quartz;@MockBean AiGateway gateway;
    @MockBean DeepSeekFiles files;
    @MockBean ModelRoute route;
    MockHttpSession session;String csrf;
    @BeforeEach void prepare()throws Exception {
        for(int i=0;i<200&&analyses.busy();i++)Thread.sleep(20);
        Path path=DATA.resolve("构造资料库-"+UUID.randomUUID());Files.createDirectories(path.resolve(".obsidian"));vault.connect(path.toString());state.put("analyses",new ArrayList<>());
        boolean initialized=body(mvc.perform(get("/api/auth/status")).andReturn()).path("initialized").asBoolean();
        MvcResult auth=mvc.perform(post(initialized?"/api/auth/login":"/api/auth/setup").contentType("application/json").content("{\"password\":\"FIXTURE_ONLY_PASSWORD\"}")).andExpect(status().isOk()).andReturn();
        session=(MockHttpSession)auth.getRequest().getSession();csrf=body(auth).path("csrf_token").asText();
        reset(gateway);when(gateway.complete(anyString(),anyString())).thenThrow(new AiGateway.MissingModelException());
    }
    JsonNode body(MvcResult r)throws Exception{return json.readTree(r.getResponse().getContentAsString()).path("data");}
    JsonNode utf8(MvcResult result)throws Exception{return json.readTree(result.getResponse().getContentAsByteArray()).path("data");}
    org.springframework.test.web.servlet.request.MockMultipartHttpServletRequestBuilder documentImport(
        byte[] bytes,String filename,String title,String mode)throws Exception {
        org.springframework.test.web.servlet.request.MockMultipartHttpServletRequestBuilder request =
            multipart("/api/documents").file(new org.springframework.mock.web.MockMultipartFile("file",filename,"text/plain",bytes));
        request.param("workspace",vault.root().toString()).param("domain","learning").param("title",title).param("mode",mode);
        return request;
    }
    List<Path> attachmentFiles()throws Exception {
        Path folder=vault.safe("99-附件/导入资料");
        if(!Files.isDirectory(folder))return Collections.emptyList();
        try(java.util.stream.Stream<Path> files=Files.walk(folder)){
            return files.filter(Files::isRegularFile).collect(java.util.stream.Collectors.toList());
        }
    }
    @Test void domainGraphsKeepLinksInsideScopeAndIncludeHealthDrafts() throws Exception {
        vault.save(map("path","30-健康/检查.md","content","---\ndomain: health\n---\n\n检查来源。"));
        vault.save(map("path","40-工作/项目.md","content","---\ndomain: work\n---\n\n[[30-健康/检查]]"));
        vault.saveReport("构造检查解读","---\ndomain: analysis\nrecord_type: exam_analysis\n---\n\n[[30-健康/检查]]");
        JsonNode health = utf8(mvc.perform(get("/api/vault/overview").param("domain","health").session(session))
            .andExpect(status().isOk()).andExpect(jsonPath("$.data.nodes.length()").value(2))
            .andExpect(jsonPath("$.data.edges[0].to").value("30-健康/检查.md"))
            .andExpect(jsonPath("$.data.total").value(1)).andReturn());
        assertEquals(6,health.path("edits").size());
        long edits = 0;
        for (JsonNode count : health.path("edits")) edits += count.asLong();
        assertEquals(1,edits);
        mvc.perform(get("/api/vault/overview").param("domain","work").session(session))
            .andExpect(status().isOk()).andExpect(jsonPath("$.data.nodes.length()").value(1))
            .andExpect(jsonPath("$.data.edges.length()").value(0));
        mvc.perform(get("/api/vault/overview").param("domain","missing").session(session)).andExpect(status().isUnprocessableEntity());
    }
    @Test void overviewAndReaderShowResolvedWikiLinksWithoutRenderingActiveContent() throws Exception {
        vault.save(map("path","主题/计划.md","content","# 下一步\n\n这是计划。"));
        vault.save(map("path","其他/计划.md","content","# 无关笔记"));
        vault.save(map("path","主题/复盘.md","content",
            "## 本周观察\n\n[[计划#下一步|打开计划]] 和缺失的 [[不存在]]\n\n`[[其他/计划]]`\n\n"
                + "| 项目 | 结果 |\n|---|---|\n| 练习 | 完成 |\n\n<script>privateMarker()</script>\n\n[unsafe](javascript:alert%281%29)\n\n![remote](https://example.invalid/pixel)"));
        mvc.perform(get("/api/vault/overview")).andExpect(status().isUnauthorized());
        mvc.perform(get("/api/vault/overview").session(session)).andExpect(status().isOk())
            .andExpect(header().string("Cache-Control","no-store"))
            .andExpect(jsonPath("$.data.nodes.length()").value(3)).andExpect(jsonPath("$.data.edges.length()").value(1));
        JsonNode reading = utf8(mvc.perform(get("/api/note").param("path","主题/复盘.md").session(session))
            .andExpect(status().isOk()).andExpect(jsonPath("$.data.outgoing.length()").value(1)).andReturn());
        String rendered = reading.path("reading_html").asText();
        assertTrue(rendered.contains("<table>"));
        assertTrue(rendered.contains("#note=%E4%B8%BB%E9%A2%98%2F%E8%AE%A1%E5%88%92.md&amp;heading="));
        assertTrue(rendered.contains("[[不存在]]"));
        assertFalse(rendered.contains("<script>"));
        assertFalse(rendered.contains("javascript:"));
        assertFalse(rendered.contains("<img"));
        mvc.perform(get("/api/note").param("path","主题/计划.md").session(session))
            .andExpect(jsonPath("$.data.incoming[0].path").value("主题/复盘.md"));
        mvc.perform(get("/api/note").param("path","其他/计划.md").session(session))
            .andExpect(jsonPath("$.data.incoming.length()").value(0));
    }
    @Test void fileImportSendsOriginalOnlyWithExplicitConsent()throws Exception {
        byte[] raw = "构造附件".getBytes(StandardCharsets.UTF_8);
        org.springframework.mock.web.MockMultipartFile file = new org.springframework.mock.web.MockMultipartFile("file","practice.md","text/plain",raw);
        org.springframework.test.web.servlet.request.MockMultipartHttpServletRequestBuilder request = multipart("/api/documents").file(file);
        request.param("workspace",vault.root().toString()).param("domain","learning").param("title","课程练习").param("mode","analyze");
        mvc.perform(request.session(session)).andExpect(status().isForbidden());
        mvc.perform(request.header("X-CSRF-Token",csrf)).andExpect(status().isUnprocessableEntity());
        verifyNoInteractions(files, gateway);
        doReturn("## 练习概览\n构造资料").when(files).analyze(any(byte[].class),eq("md"),anyString());
        String archived = utf8(mvc.perform(request.param("consent","true")).andExpect(status().isOk()).andReturn()).path("path").asText();
        VaultNote draft = vault.read(archived);
        assertEquals("draft", draft.properties.get("status"));
        assertTrue(draft.body.contains("练习概览"));
        assertFalse(draft.eligibleForAi());
        assertEquals(1, vault.notes().size());
        mvc.perform(get("/api/documents/original").param("path",archived)).andExpect(status().isUnauthorized());
        mvc.perform(get("/api/documents/original").session(session).param("path",archived)).andExpect(content().bytes(raw))
            .andExpect(header().string("Cache-Control","no-store"));
        verify(files).analyze(aryEq(raw),eq("md"),anyString());
        verifyNoInteractions(gateway);
    }

    @Test void repeatedDocumentImportCreatesIndependentSearchableCopies()throws Exception {
        // 当前实现不去重：每次导入生成新的 UUID，因此同一原件会得到两份独立笔记与附件。
        byte[] raw = "构造重复导入原件".getBytes(StandardCharsets.UTF_8);
        String title = "重复导入构造资料";
        String first = utf8(mvc.perform(documentImport(raw,"repeat.txt",title,"archive").session(session).header("X-CSRF-Token",csrf))
            .andExpect(status().isOk()).andReturn()).path("path").asText();
        String second = utf8(mvc.perform(documentImport(raw,"repeat.txt",title,"archive").session(session).header("X-CSRF-Token",csrf))
            .andExpect(status().isOk()).andReturn()).path("path").asText();
        assertNotEquals(first,second);
        assertEquals(2,vault.notes().size());
        assertEquals(2,attachmentFiles().size());
        VaultNote firstNote = vault.read(first), secondNote = vault.read(second);
        assertNotEquals(firstNote.properties.get("attachment"),secondNote.properties.get("attachment"));
        for(VaultNote note:Arrays.asList(firstNote,secondNote)){
            assertEquals("imported_document",note.properties.get("record_type"));
            assertEquals("historical",note.properties.get("status"));
            assertEquals(VaultService.hash(raw),note.properties.get("attachment_sha256"));
            assertTrue(Files.isRegularFile(vault.safe(String.valueOf(note.properties.get("attachment")))));
            mvc.perform(get("/api/documents/original").session(session).param("path",note.path))
                .andExpect(status().isOk()).andExpect(content().bytes(raw));
        }
        // /api/notes 直接读取当前 Vault；导入后无需额外重建索引即可按标题检索到两份记录。
        assertEquals(2,utf8(mvc.perform(get("/api/notes").session(session).param("q",title))
            .andExpect(status().isOk()).andReturn()).path("total").asInt());
    }

    @Test void failedDocumentImportLeavesNoOrphanAttachment()throws Exception {
        // 让笔记正文超过 5MB：附件已写入后，vault.save 拒绝笔记，save 的失败分支必须删除附件。
        byte[] raw = "构造失败原件".getBytes(StandardCharsets.UTF_8);
        char[] filler = new char[5 * 1024 * 1024 + 1];
        Arrays.fill(filler,'x');
        doReturn(new String(filler)).when(files).analyze(any(byte[].class),eq("txt"),anyString());
        mvc.perform(documentImport(raw,"fail.txt","失败导入构造资料","analyze").param("consent","true")
                .session(session).header("X-CSRF-Token",csrf))
            .andExpect(status().isUnprocessableEntity()).andExpect(jsonPath("$.success").value(false))
            .andExpect(jsonPath("$.message").value("笔记不能为空，且不能超过5MB"));
        assertTrue(vault.notes().isEmpty());
        assertTrue(attachmentFiles().isEmpty());
        verify(files).analyze(aryEq(raw),eq("txt"),anyString());
        verifyNoInteractions(gateway);
    }

    @Test void importedDraftIsSearchableWithoutExplicitIndexRebuild()throws Exception {
        // 本模块没有独立索引或重建接口；/api/notes 每次扫描当前 Vault，因此导入后立即可检索。
        byte[] raw = "构造检索原件".getBytes(StandardCharsets.UTF_8);
        doReturn("## 整理\n构造检索正文标记").when(files).analyze(any(byte[].class),eq("txt"),anyString());
        String path = utf8(mvc.perform(documentImport(raw,"search.txt","构造检索标题","analyze").param("consent","true")
                .session(session).header("X-CSRF-Token",csrf))
            .andExpect(status().isOk()).andReturn()).path("path").asText();
        JsonNode found = utf8(mvc.perform(get("/api/notes").session(session).param("q","构造检索正文标记"))
            .andExpect(status().isOk()).andReturn());
        assertEquals(1,found.path("total").asInt());
        assertEquals(path,found.path("items").get(0).path("path").asText());
        verify(files).analyze(aryEq(raw),eq("txt"),anyString());
        verifyNoInteractions(gateway);
    }

    @Test void examBatchItemRetryReusesRecordWithoutChangingOtherYears() throws Exception {
        byte[] bytes = "构造体检记录".getBytes(StandardCharsets.UTF_8);
        org.springframework.mock.web.MockMultipartFile file = new org.springframework.mock.web.MockMultipartFile("file","exam.txt","text/plain",bytes);
        String oldId = UUID.randomUUID().toString();
        String newId = UUID.randomUUID().toString();
        for (String id : Arrays.asList(oldId, newId, oldId)) {
            mvc.perform(multipart("/api/exams").file(file).session(session).header("X-CSRF-Token",csrf)
                .param("workspace",vault.root().toString()).param("date",id.equals(oldId) ? "2022-03-14" : "2025-06-15")
                .param("mode","archive").param("import_id",id))
                .andExpect(status().isOk()).andExpect(jsonPath("$.data.id").value(id));
        }
        mvc.perform(multipart("/api/exams").file(file).session(session).header("X-CSRF-Token",csrf)
            .param("workspace",vault.root().toString()).param("date","2024-01-01").param("mode","archive").param("import_id",oldId))
            .andExpect(status().isConflict());
        org.springframework.mock.web.MockMultipartFile different = new org.springframework.mock.web.MockMultipartFile("file","exam.txt","text/plain",new byte[]{1,2,3});
        mvc.perform(multipart("/api/exams").file(different).session(session).header("X-CSRF-Token",csrf)
            .param("workspace",vault.root().toString()).param("date","2022-03-14").param("mode","archive").param("import_id",oldId))
            .andExpect(status().isConflict());
        mvc.perform(get("/api/exams").session(session)).andExpect(status().isOk())
            .andExpect(jsonPath("$.data.reports.length()").value(2))
            .andExpect(jsonPath("$.data.reports[0].id").value(newId))
            .andExpect(jsonPath("$.data.reports[1].id").value(oldId));
        mvc.perform(get("/api/exams/"+oldId+"/original").session(session)).andExpect(content().bytes(bytes));
        verifyNoInteractions(files,gateway);
    }

    @Test void examArchiveOnlyKeepsOriginalAndCanAnalyzeLater()throws Exception {
        byte[] original;
        try (org.apache.pdfbox.pdmodel.PDDocument pdf = new org.apache.pdfbox.pdmodel.PDDocument();
             java.io.ByteArrayOutputStream bytes = new java.io.ByteArrayOutputStream()) {
            addPdfLine(pdf, "Synthetic screening results");
            pdf.addPage(new org.apache.pdfbox.pdmodel.PDPage());
            pdf.save(bytes);
            original = bytes.toByteArray();
        }
        org.springframework.mock.web.MockMultipartFile file = new org.springframework.mock.web.MockMultipartFile("file","exam.pdf","application/pdf",original);
        JsonNode saved = utf8(mvc.perform(multipart("/api/exams").file(file).session(session).header("X-CSRF-Token",csrf)
            .param("workspace",vault.root().toString()).param("date","2024-02-18").param("mode","archive"))
            .andExpect(status().isOk()).andReturn());
        String endpoint = "/api/exams/" + saved.path("id").asText();
        verifyNoInteractions(files);
        mvc.perform(get(endpoint+"/original").session(session)).andExpect(content().bytes(original));
        mvc.perform(get(endpoint+"/preview").session(session)).andExpect(status().isOk())
            .andExpect(jsonPath("$.data.mode").value("original"))
            .andExpect(jsonPath("$.data.readable_pages").value(1))
            .andExpect(jsonPath("$.data.page_count").value(2));
        Map<String,Object> input = map("revision",saved.path("revision").asText(),"consent",true,"workspace",vault.root().toString());
        String payload = json.writeValueAsString(input);
        mvc.perform(post(endpoint+"/analysis").session(session).header("X-CSRF-Token",csrf).contentType("application/json").content("{}"))
            .andExpect(status().isUnprocessableEntity());
        input.put("evidence_mode","pdf_text");
        mvc.perform(post(endpoint+"/analysis").session(session).header("X-CSRF-Token",csrf)
            .contentType("application/json").content(json.writeValueAsString(input))).andExpect(status().isConflict());
        verifyNoInteractions(files);
        String legacyName = "体检/" + saved.path("id").asText() + "-" + saved.path("revision").asText();
        vault.saveReport(legacyName, "---\ndomain: analysis\nfindings: {\"summary\":\"旧版构造解读\"}\n---\n");
        mvc.perform(get(endpoint).session(session)).andExpect(status().isOk())
            .andExpect(jsonPath("$.data.analysis_version").value(1));
        doReturn(examDraft()).when(files).analyze(any(byte[].class),eq("pdf"),anyString());
        JsonNode analysis = utf8(mvc.perform(post(endpoint+"/analysis").session(session).header("X-CSRF-Token",csrf)
            .contentType("application/json").content(payload)).andExpect(status().isOk()).andReturn());
        assertEquals("第 2 页", analysis.path("findings").path("metrics").get(0).path("location").asText());
        assertEquals(3, analysis.path("analysis_version").asInt());
        assertEquals("按报告建议复核。", analysis.path("findings").path("recommendations").get(0).path("quote").asText());
        assertEquals("80-AI分析/" + legacyName + "-v3.md", analysis.path("report_path").asText());
        assertEquals("80-AI分析/" + legacyName + ".md", analysis.path("previous_report_path").asText());
        assertTrue(java.nio.file.Files.isRegularFile(vault.root().resolve("80-AI分析/" + legacyName + ".md")));
        assertFalse(vault.read(analysis.path("report_path").asText()).eligibleForAi());
        mvc.perform(post(endpoint+"/analysis").session(session).header("X-CSRF-Token",csrf)
            .contentType("application/json").content(payload)).andExpect(status().isOk());
        verify(files).analyze(aryEq(original),eq("pdf"),anyString());
        verifyNoInteractions(gateway);
    }

    @Test void foreignCurrentExamDraftIsIgnoredAndBlocksAnalysisWithoutModelCall()throws Exception {
        // 新版路径被一份来源不匹配的构造报告占用。
        byte[] original = "构造体检原件，仅用于草稿路径占用测试。".getBytes(StandardCharsets.UTF_8);
        org.springframework.mock.web.MockMultipartFile file = new org.springframework.mock.web.MockMultipartFile("file","exam.txt","text/plain",original);
        JsonNode saved = utf8(mvc.perform(multipart("/api/exams").file(file).session(session).header("X-CSRF-Token",csrf)
            .param("workspace",vault.root().toString()).param("date","2024-02-18").param("mode","archive"))
            .andExpect(status().isOk()).andReturn());
        String id = saved.path("id").asText(), revision = saved.path("revision").asText();
        String endpoint = "/api/exams/" + id;
        String legacyName = "体检/" + id + "-" + revision;
        String legacyPath = "80-AI分析/" + legacyName + ".md";
        String occupiedPath = "80-AI分析/" + legacyName + "-v3.md";
        vault.saveReport(legacyName + "-v3", "---\ndomain: analysis\nrecord_type: exam_analysis\n"
            + "source_revision: wrong-source-revision\nfindings: {\"summary\":\"外来构造草稿\"}\n---\n\n外来内容不得覆盖。\n");

        JsonNode withoutLegacy = utf8(mvc.perform(get(endpoint).session(session)).andExpect(status().isOk()).andReturn());
        assertEquals(0,withoutLegacy.path("analysis_version").asInt());
        assertTrue(withoutLegacy.path("report_path").isNull() || withoutLegacy.path("report_path").isMissingNode());
        assertTrue(withoutLegacy.path("findings").isNull() || withoutLegacy.path("findings").isMissingNode());

        vault.saveReport(legacyName, "---\ndomain: analysis\nfindings: {\"summary\":\"旧版构造解读\"}\n---\n");
        mvc.perform(get(endpoint).session(session)).andExpect(status().isOk())
            .andExpect(jsonPath("$.data.analysis_version").value(1))
            .andExpect(jsonPath("$.data.report_path").value(legacyPath));

        byte[] occupied = Files.readAllBytes(vault.safe(occupiedPath));
        byte[] legacy = Files.readAllBytes(vault.safe(legacyPath));
        String payload = json.writeValueAsString(map("revision",revision,"consent",true,"workspace",vault.root().toString()));
        mvc.perform(post(endpoint+"/analysis").session(session).header("X-CSRF-Token",csrf)
                .contentType("application/json").content(payload))
            .andExpect(status().isConflict()).andExpect(jsonPath("$.success").value(false))
            .andExpect(jsonPath("$.message").value("体检分析草稿路径已被其他内容占用，请先备份并移走该文件后重试"));
        verifyNoInteractions(files, gateway);
        assertArrayEquals(occupied,Files.readAllBytes(vault.safe(occupiedPath)));
        assertArrayEquals(legacy,Files.readAllBytes(vault.safe(legacyPath)));
        mvc.perform(get(endpoint).session(session)).andExpect(status().isOk())
            .andExpect(jsonPath("$.data.report_path").value(legacyPath));
    }

    @Test void searchableExamPdfUsesLocalPageTextAndChecksCitations() throws Exception {
        byte[] original;
        try (org.apache.pdfbox.pdmodel.PDDocument pdf = new org.apache.pdfbox.pdmodel.PDDocument();
             java.io.ByteArrayOutputStream bytes = new java.io.ByteArrayOutputStream()) {
            addPdfLine(pdf, "Synthetic screening results");
            addPdfLine(pdf, "TEST ALT 62 U/L 8-40 H");
            pdf.save(bytes);
            original = bytes.toByteArray();
        }
        org.springframework.mock.web.MockMultipartFile file = new org.springframework.mock.web.MockMultipartFile("file","exam.pdf","application/pdf",original);
        JsonNode saved = utf8(mvc.perform(multipart("/api/exams").file(file).session(session).header("X-CSRF-Token",csrf)
            .param("workspace",vault.root().toString()).param("date","2024-02-18").param("mode","archive"))
            .andExpect(status().isOk()).andReturn());
        String endpoint = "/api/exams/" + saved.path("id").asText();
        mvc.perform(get(endpoint+"/preview")).andExpect(status().isUnauthorized());
        mvc.perform(get(endpoint+"/preview").session(session)).andExpect(status().isOk())
            .andExpect(jsonPath("$.data.mode").value("pdf_text"))
            .andExpect(jsonPath("$.data.pages[1].text").value("TEST ALT 62 U/L 8-40 H"));
        verifyNoInteractions(files,gateway);
        String payload = json.writeValueAsString(map("revision",saved.path("revision").asText(),"consent",true,
            "workspace",vault.root().toString(),"evidence_mode","pdf_text"));
        String goodDraft = json.writeValueAsString(map("summary","构造解读","questions",Collections.emptyList(),
            "limitations",Collections.emptyList(),"observations",Collections.emptyList(),"recommendations",Collections.emptyList(),
            "metrics",Collections.singletonList(map("name","TEST ALT","value","62","unit","U/L","range","8-40",
                "flag","H","quote","TEST ALT 62 U/L 8-40 H","location","第 1 页"))));
        doReturn(goodDraft.replace("62","63"),goodDraft).when(gateway).complete(anyString(),anyString());
        mvc.perform(post(endpoint+"/analysis").session(session).header("X-CSRF-Token",csrf)
            .contentType("application/json").content(payload)).andExpect(status().isBadGateway());
        mvc.perform(post(endpoint+"/analysis").session(session).header("X-CSRF-Token",csrf)
            .contentType("application/json").content(payload)).andExpect(status().isOk())
            .andExpect(jsonPath("$.data.findings.metrics[0].location").value("第 2 页"))
            .andExpect(jsonPath("$.data.findings.textEvidenceVerified").value(true));
        verify(gateway,times(2)).complete(anyString(),contains("[第 2 页]\nTEST ALT 62 U/L 8-40 H"));
        verifyNoInteractions(files);
    }

    private void addPdfLine(org.apache.pdfbox.pdmodel.PDDocument pdf, String line) throws Exception {
        org.apache.pdfbox.pdmodel.PDPage page = new org.apache.pdfbox.pdmodel.PDPage();
        pdf.addPage(page);
        try (org.apache.pdfbox.pdmodel.PDPageContentStream stream = new org.apache.pdfbox.pdmodel.PDPageContentStream(pdf,page)) {
            stream.beginText();
            stream.setFont(org.apache.pdfbox.pdmodel.font.PDType1Font.HELVETICA,12);
            stream.newLineAtOffset(40,720);
            stream.showText(line);
            stream.endText();
        }
    }

    @Test void examTextRejectsModelQuoteMissingFromOriginal() throws Exception {
        byte[] original = "构造文本，含有不同的检查记录。".getBytes(StandardCharsets.UTF_8);
        org.springframework.mock.web.MockMultipartFile file = new org.springframework.mock.web.MockMultipartFile("file","exam.txt","text/plain",original);
        JsonNode saved = utf8(mvc.perform(multipart("/api/exams").file(file).session(session).header("X-CSRF-Token",csrf)
            .param("workspace",vault.root().toString()).param("date","2024-02-18").param("mode","archive"))
            .andExpect(status().isOk()).andReturn());
        String endpoint = "/api/exams/" + saved.path("id").asText();
        String payload = json.writeValueAsString(map("revision",saved.path("revision").asText(),"consent",true,"workspace",vault.root().toString()));
        doReturn(examDraft()).when(files).analyze(aryEq(original),eq("txt"),anyString());
        mvc.perform(post(endpoint+"/analysis").session(session).header("X-CSRF-Token",csrf)
            .contentType("application/json").content(payload)).andExpect(status().isBadGateway());
        mvc.perform(get(endpoint).session(session)).andExpect(status().isOk())
            .andExpect(jsonPath("$.data.analysis_version").value(0));
        mvc.perform(get(endpoint+"/original").session(session)).andExpect(content().bytes(original));
    }

    @Test void examImportKeepsOriginalWhenProviderFails()throws Exception {
        byte[] original = "构造图片占位".getBytes(StandardCharsets.UTF_8);
        org.springframework.mock.web.MockMultipartFile file = new org.springframework.mock.web.MockMultipartFile("file","exam.jpg","image/jpeg",original);
        doThrow(new org.springframework.web.server.ResponseStatusException(org.springframework.http.HttpStatus.BAD_GATEWAY,"测试替身暂不可用"))
            .when(files).analyze(any(byte[].class),eq("jpg"),anyString());
        JsonNode saved = utf8(mvc.perform(multipart("/api/exams").file(file).session(session).header("X-CSRF-Token",csrf)
            .param("workspace",vault.root().toString()).param("date","2024-02-18").param("mode","analyze").param("consent","true"))
            .andExpect(status().isOk()).andReturn());
        assertEquals("测试替身暂不可用", saved.path("warning").asText());
        mvc.perform(get("/api/exams/"+saved.path("id").asText()+"/original").session(session)).andExpect(content().bytes(original));
        assertEquals(1, vault.notes().size());
    }

    String examDraft() throws Exception {
        return json.writeValueAsString(map("summary","构造解读","questions",Collections.emptyList(),
            "limitations",Collections.singletonList("报告未注明检测方法。"),
            "observations",Collections.singletonList(map("quote","构造指标 12 U/L 8-10 ↑","location","第 2 页",
                "interpretation","数值超出原报告参考区间。")),
            "recommendations",Collections.singletonList(map("quote","按报告建议复核。","location","第 3 页")),
            "metrics",Collections.singletonList(map("name","构造指标","value","12","unit","U/L","range","8-10",
                "flag","↑","quote","构造指标 12 U/L 8-10 ↑","location","第 2 页"))));
    }
    VaultNote fixture(String domain,String body)throws Exception {
        return vault.save(map("domain",domain,"content","---\ntitle: 构造资料（仅测试）\ndomain: "+domain+"\nstatus: current\nobserved_at: \"2024-01-01\"\nsource: 测试替身\n---\n\n"+body));
    }
    Map<String,Object> request(VaultNote n){return map("question","请整理构造资料的缺失信息","sources",Arrays.asList(map("path",n.path,"revision",n.revision)),"consent",true);}
    Map<String,Object> waitFor(String id)throws Exception {
        for(int i=0;i<200;i++){Map<String,Object> j=analyses.history().stream().filter(x->id.equals(x.get("id"))).findFirst().get();if(!Arrays.asList("running","queued").contains(j.get("status")))return j;Thread.sleep(25);}throw new AssertionError("分析替身未完成");
    }
    @Test void localAccessAndPrivateQuartzRequireAuthentication()throws Exception {
        mvc.perform(get("/api/health")).andExpect(status().isOk()).andExpect(jsonPath("$.success").value(true)).andExpect(jsonPath("$.service").value("personal-agent"));
        mvc.perform(get("/api/notes")).andExpect(status().isUnauthorized());
        mvc.perform(get("/library/static/contentIndex.json")).andExpect(status().isFound()).andExpect(header().string("Location","/"));
        mvc.perform(get("/api/vault").with(r->{r.setRemoteAddr("192.0.2.1");return r;})).andExpect(status().isForbidden());
        mvc.perform(post("/api/vault/initialize").session(session).contentType("application/json").content("{}")).andExpect(status().isForbidden());
        mvc.perform(get("/api/vault").session(session).header("Origin","https://example.invalid")).andExpect(status().isForbidden());
    }
    @Test void homepageNavigationExceptionDoesNotApplyToApiOrIframe()throws Exception {
        mvc.perform(get("/").header("Sec-Fetch-Site","cross-site").header("Sec-Fetch-Mode","navigate").header("Sec-Fetch-Dest","document")).andExpect(status().isOk());
        mvc.perform(get("/api/vault").session(session).header("Sec-Fetch-Site","cross-site").header("Sec-Fetch-Mode","navigate").header("Sec-Fetch-Dest","document")).andExpect(status().isForbidden());
        mvc.perform(get("/").header("Sec-Fetch-Site","cross-site").header("Sec-Fetch-Mode","navigate").header("Sec-Fetch-Dest","iframe")).andExpect(status().isForbidden());
    }
    @Test void obsidianExternalEditsAreVisibleAndOptimisticWritesPreserveThem()throws Exception {
        VaultNote original=fixture("health","构造健康资料，不代表真实用户");Path file=vault.safe(original.path);
        Files.write(file,(original.content+"\n外部 Obsidian 修改\n").getBytes(StandardCharsets.UTF_8));
        mvc.perform(get("/api/notes").session(session).param("q","外部 Obsidian")).andExpect(jsonPath("$.data.total").value(1));
        mvc.perform(post("/api/notes").session(session).header("X-CSRF-Token",csrf).contentType("application/json")
            .content(json.writeValueAsString(map("path",original.path,"content",original.content,"expected_revision",original.revision)))).andExpect(status().isConflict());
        assertTrue(vault.read(original.path).body.contains("外部 Obsidian"));
    }
    @Test void successfulEditBacksUpOriginalAndRetainsProperties()throws Exception {
        VaultNote old=fixture("work","原始构造记录");vault.save(map("path",old.path,"content",old.content+"\n[[另一篇笔记]]","expected_revision",old.revision));
        assertEquals("2024-01-01",vault.read(old.path).properties.get("observed_at"));assertEquals("另一篇笔记",vault.read(old.path).links.get(0));
        try(java.util.stream.Stream<Path> backups=Files.list(DATA.resolve("note-backups"))){assertTrue(backups.anyMatch(p->{try{return new String(Files.readAllBytes(p),StandardCharsets.UTF_8).equals(old.content);}catch(Exception e){return false;}}));}
    }
    @Test void pathTraversalAndHiddenDirectoriesAreRejected()throws Exception {
        assertThrows(Exception.class,()->vault.read("../knowledge-state.json"));assertThrows(Exception.class,()->vault.read(".obsidian/config.md"));
        assertThrows(Exception.class,()->vault.save(map("path","../../outside.md","content","构造内容")));
        Path hidden=vault.root().resolve(".secret");Files.createDirectories(hidden);Files.write(hidden.resolve("hidden.md"),"不应索引".getBytes(StandardCharsets.UTF_8));assertTrue(vault.notes().isEmpty());
    }
    @Test void symbolicFileCannotReadOutsideVault()throws Exception {
        Path outside=DATA.resolve("outside.md");Files.write(outside,"仅测试越界".getBytes(StandardCharsets.UTF_8));
        try{Files.createSymbolicLink(vault.root().resolve("escape.md"),outside);}catch(Exception e){Assumptions.assumeTrue(false,"当前 Windows 账户无创建符号链接权限");}
        assertThrows(Exception.class,()->vault.read("escape.md"));assertTrue(vault.notes().isEmpty());
    }
    @Test void yamlConstructorsAndDuplicateKeysAreRejected() {
        assertThrows(Exception.class,()->vault.parse("unsafe.md","---\nx: !!java.net.URL [https://example.invalid]\n---\n测试"));
        assertThrows(Exception.class,()->vault.parse("duplicate.md","---\ntitle: A\ntitle: B\n---\n测试"));
    }
    @Test void initializationIsIdempotentAndNeverInventsPersonalValues()throws Exception {
        vault.initialize();String first=vault.fingerprint();vault.initialize();assertEquals(first,vault.fingerprint());
        assertTrue(Files.isDirectory(vault.root().resolve(".obsidian")));assertTrue(vault.notes().stream().noneMatch(VaultNote::eligibleForAi));
    }
    @Test void previewExcludesDraftsReportsAndExplicitPrivateNotes()throws Exception {
        fixture("finance","可用构造记录");vault.save(map("domain","finance","content","---\ntitle: 禁用\nai_exclude: true\n---\n不可发送"));
        vault.saveReport("fake-report","---\ntitle: 派生报告\norigin: ai_generated\n---\n不可作为事实");
        Map<String,Object> preview=analyses.preview("构造","finance");assertEquals(1,((List<?>)preview.get("sources")).size());
    }
    @Test void consentAndUnchangedSourceRevisionsAreRequired()throws Exception {
        VaultNote n=fixture("work","构造工作记录");Map<String,Object> input=request(n);input.put("consent",false);assertThrows(Exception.class,()->analyses.start(input));
        input.put("consent",true);Files.write(vault.safe(n.path),(n.content+"\nchanged").getBytes(StandardCharsets.UTF_8));assertThrows(Exception.class,()->analyses.start(input));verifyNoInteractions(gateway);
    }
    @Test void reportHasVersionedCitationsAndNeverRewritesFacts()throws Exception {
        VaultNote n=fixture("finance","金额是构造数据，币种与日期有待核对");doReturn("## 已知事实\n资料需要补全币种 [S1]。\n\n## 建议\n先补全资料。").when(gateway).complete(anyString(),anyString());
        Map<String,Object> result=waitFor(text(analyses.start(request(n)),"id"));assertEquals("completed",result.get("status"));
        assertEquals(n.revision,vault.read(n.path).revision);VaultNote report=vault.read(text(result,"report_path"));
        assertEquals("draft",report.properties.get("status"));assertFalse(report.eligibleForAi());assertTrue(report.body.contains(n.revision));assertTrue(report.body.contains("[["+n.path));
        verify(gateway).complete(contains("历史快照不可当作今天情况"),contains("2024-01-01"));
    }
    @Test void missingModelProducesNoFabricatedReport()throws Exception {
        VaultNote n=fixture("health","构造健康记录");Map<String,Object> result=waitFor(text(analyses.start(request(n)),"id"));
        assertEquals("waiting_configuration",result.get("status"));assertNull(result.get("report_path"));assertEquals(1,vault.notes().size());
    }
    @Test void outOfRangeModelCitationsAreMarkedForReview()throws Exception {
        VaultNote n=fixture("work","构造记录");doReturn("不受支持的引用 [S99]").when(gateway).complete(anyString(),anyString());
        Map<String,Object> result=waitFor(text(analyses.start(request(n)),"id"));assertEquals(true,result.get("invalid_citations"));
    }
    @Test void staleQuartzArtifactsFailClosedIncludingSearchIndex()throws Exception {
        fixture("life","构造生活记录");String revision=vault.fingerprint();Path site=DATA.resolve("quartz-builds/fixture/site");Files.createDirectories(site.resolve("static"));
        Files.write(site.resolve("index.html"),"<h1>仅测试</h1>".getBytes(StandardCharsets.UTF_8));Files.write(site.resolve("static/contentIndex.json"),"{}".getBytes(StandardCharsets.UTF_8));
        state.put("quartz_publication",map("id","fixture","revision",revision,"published_at",now()));
        mvc.perform(get("/library/").session(session)).andExpect(status().isOk());
        fixture("work","新增构造记录");mvc.perform(get("/library/static/contentIndex.json").session(session)).andExpect(status().isConflict());
    }
    @Test void switchingVaultDoesNotMoveOriginalFiles()throws Exception {
        VaultNote n=fixture("life","原仓库资料");Path original=vault.root();Path next=DATA.resolve("next-"+UUID.randomUUID());Files.createDirectories(next.resolve(".obsidian"));
        vault.connect(next.toString());assertTrue(vault.notes().isEmpty());assertTrue(Files.exists(original.resolve(n.path)));assertNull(state.get("quartz_publication"));
    }
}
