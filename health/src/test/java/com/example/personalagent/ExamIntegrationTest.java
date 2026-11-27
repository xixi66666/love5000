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

import com.example.health.HealthApplication;
@SpringBootTest(classes=HealthApplication.class,properties="logging.level.root=WARN")
@AutoConfigureMockMvc
class ExamIntegrationTest {
    static final Path DATA=Paths.get("target","test-health-"+UUID.randomUUID()).toAbsolutePath();
    @DynamicPropertySource static void properties(DynamicPropertyRegistry r){
        r.add("agent.data-dir",()->DATA.toString()); r.add("agent.legacy-state-dir",()->DATA.resolve("empty-legacy").toString());
        // 测试必须显式隔离 Vault，不能创建或使用 D 盘的真实个人资料库。
        r.add("agent.vault-dir",()->DATA.resolve("default-vault").toString());
    }
    @Autowired MockMvc mvc;@Autowired ObjectMapper json;@Autowired VaultService vault;@Autowired WorkspaceState state;
    @MockBean AiGateway gateway;
    @MockBean DeepSeekFiles files;
    @MockBean ModelRoute route;
    @MockBean MirobodyEngine engine;
    MockHttpSession session;String csrf;
    @BeforeEach void prepare()throws Exception {

        Path path=DATA.resolve("构造资料库-"+UUID.randomUUID());Files.createDirectories(path.resolve(".obsidian"));vault.connect(path.toString());
        boolean initialized=body(mvc.perform(get("/api/auth/status")).andReturn()).path("initialized").asBoolean();
        MvcResult auth=mvc.perform(post(initialized?"/api/auth/login":"/api/auth/setup").contentType("application/json").content("{\"password\":\"FIXTURE_ONLY_PASSWORD\"}")).andExpect(status().isOk()).andReturn();
        session=(MockHttpSession)auth.getRequest().getSession();csrf=body(auth).path("csrf_token").asText();
        reset(gateway);when(gateway.complete(anyString(),anyString())).thenThrow(new AiGateway.MissingModelException());
    }
    JsonNode body(MvcResult r)throws Exception{return json.readTree(r.getResponse().getContentAsString()).path("data");}
    JsonNode utf8(MvcResult result)throws Exception{return json.readTree(result.getResponse().getContentAsByteArray()).path("data");}

    @Test void firstStartupAdoptsVaultAndLoginWithoutWritingLegacyState() throws Exception {
        Path oldDirectory = Files.createDirectories(DATA.resolve("legacy-"+UUID.randomUUID()));
        Path newDirectory = DATA.resolve("separate-"+UUID.randomUUID());
        Path oldFile = oldDirectory.resolve("knowledge-state.json");
        Map<String,Object> credentials = map("salt","synthetic-salt","hash","synthetic-hash");
        byte[] before = json.writeValueAsBytes(map("vault_path",vault.root().toString(),"auth",credentials,"quartz_publication",map("private","fixture")));
        Files.write(oldFile,before);
        AgentConfig config = new AgentConfig(); config.setExamOwner(true); config.setDataDir(newDirectory.toString());
        config.setLegacyStateDir(oldDirectory.toString());
        WorkspaceState separate = new WorkspaceState(config,json);
        try {
            assertEquals(vault.root().toString(),separate.get("vault_path"));
            assertEquals(credentials,separate.get("auth"));
            assertNull(separate.get("quartz_publication"));
            assertArrayEquals(before,Files.readAllBytes(oldFile));
        } finally { separate.close(); }
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
        assertEquals(4, analysis.path("analysis_version").asInt());
        assertEquals("按报告建议复核。", analysis.path("findings").path("recommendations").get(0).path("quote").asText());
        assertEquals("80-AI分析/" + legacyName + "-v4.md", analysis.path("report_path").asText());
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
        String occupiedPath = "80-AI分析/" + legacyName + "-v4.md";
        vault.saveReport(legacyName + "-v4", "---\ndomain: analysis\nrecord_type: exam_analysis\n"
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
        Map<String,Object> valid = map("name","TEST ALT","value","62","unit","U/L","range","8-40","flag","H","page",2,"start",1,"end",1);
        Map<String,Object> invalid = new LinkedHashMap<>(valid);
        invalid.put("value","63");
        Map<String,Object> draft = map("questions",Collections.emptyList(),"limitations",Collections.emptyList(),
            "observations",Collections.emptyList(),"recommendations",Collections.emptyList(),"metrics",Collections.singletonList(invalid));
        String rejected = json.writeValueAsString(draft);
        draft.put("metrics", Arrays.asList(valid,invalid));
        draft.put("observations",Collections.singletonList(map("page",2,"start",1,"end",1,"category","lab",
            "interpretation","合成报告记录了此项结果。","uncertainty","构造数据仅供测试。")));
        doReturn(rejected,json.writeValueAsString(draft)).when(gateway).completeExam(anyString(),anyString());
        mvc.perform(post(endpoint+"/analysis").session(session).header("X-CSRF-Token",csrf)
            .contentType("application/json").content(payload)).andExpect(status().isBadGateway());
        mvc.perform(post(endpoint+"/analysis").session(session).header("X-CSRF-Token",csrf)
            .contentType("application/json").content(payload)).andExpect(status().isOk())
            .andExpect(jsonPath("$.data.findings.metrics[0].location").value("第 2 页"))
            .andExpect(jsonPath("$.data.findings.metrics[0].quote").value("TEST ALT 62 U/L 8-40 H"))
            .andExpect(jsonPath("$.data.findings.metrics.length()").value(1))
            .andExpect(jsonPath("$.data.findings.omittedEvidence").value(1))
            .andExpect(jsonPath("$.data.findings.observations[0].category").value("lab"))
            .andExpect(jsonPath("$.data.findings.textEvidenceVerified").value(true));
        verify(gateway,times(2)).completeExam(anyString(),contains("[第 2 页]\n2.1 TEST ALT 62 U/L 8-40 H"));
        verifyNoInteractions(files);
    }

    @Test void timelineLinksVerifiedV3EvidenceAcrossDatesWithoutMergingIncompatibleMeasurements() throws Exception {
        timelineExam("2021-01-01",true, Arrays.asList(timelineMetric("HCT","40","%"),timelineMetric("红细胞压积","41","%")), "");
        String first = timelineExam("2022-05-11",true, Collections.singletonList(timelineMetric("红细胞压积HCT","40.1","%")), "构造左肺小结节记录。");
        timelineExam("2023-07-04",true, Collections.singletonList(timelineMetric("HCT","42.3","%")), "构造右肺小结节记录。");
        timelineExam("2024-04-12",true, Collections.singletonList(timelineMetric("HCT","0.43","L/L")), "");
        timelineExam("2025-05-12",false, Collections.singletonList(timelineMetric("HCT","44.2","%")), "构造左肺结节记录。");
        mvc.perform(get("/api/exams/timeline")).andExpect(status().isUnauthorized());
        mvc.perform(get("/api/exams/timeline").session(session)).andExpect(status().isOk())
            .andExpect(jsonPath("$.data.reports.length()").value(5))
            .andExpect(jsonPath("$.data.verified_report_count").value(4))
            .andExpect(jsonPath("$.data.metrics.length()").value(1))
            .andExpect(jsonPath("$.data.metrics[0].label").value("红细胞压积"))
            .andExpect(jsonPath("$.data.metrics[0].status").value("normal"))
            .andExpect(jsonPath("$.data.metrics[0].points.length()").value(2))
            .andExpect(jsonPath("$.data.metrics[0].points[0].exam_id").value(first))
            .andExpect(jsonPath("$.data.metrics[0].points[1].value").value("42.3"))
            .andExpect(jsonPath("$.data.metrics[0].change").value("2.2"))
            .andExpect(jsonPath("$.data.individual_metrics.length()").value(3))
            .andExpect(jsonPath("$.data.topics[0].label").value("肺结节"))
            .andExpect(jsonPath("$.data.topics[0].points.length()").value(2))
            .andExpect(jsonPath("$.data.topics[0].points[1].quote").value("构造右肺小结节记录。"));
        verifyNoInteractions(files,gateway);
    }

    @Test void localDocumentAndAuthorizedOcrPreserveSeparateDraftsAndTimelineEvidence() throws Exception {
        byte[] original;
        try (org.apache.pdfbox.pdmodel.PDDocument pdf = new org.apache.pdfbox.pdmodel.PDDocument();
             java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream()) {
            addPdfLine(pdf,"TEST ALT 62 U/L 8-40 H");
            pdf.save(out);
            original = out.toByteArray();
        }
        JsonNode saved = utf8(mvc.perform(multipart("/api/exams").file(new org.springframework.mock.web.MockMultipartFile(
            "file","exam.pdf","application/pdf",original)).session(session).header("X-CSRF-Token",csrf)
            .param("workspace",vault.root().toString()).param("date","2025-03-21").param("mode","archive"))
            .andExpect(status().isOk()).andReturn());
        String endpoint = "/api/exams/" + saved.path("id").asText();
        when(engine.available()).thenReturn(true);
        JsonNode reply = json.valueToTree(map("metrics",Collections.singletonList(
            classificationMetric("ALT","62","U/L","8-40","H","TEST ALT 62 U/L 8-40 H"))));
        ((com.fasterxml.jackson.databind.node.ObjectNode)reply.path("metrics").get(0)).put("location","第 1 页");
        when(engine.parse(aryEq(original),eq("pdf"))).thenReturn(reply);
        when(engine.parseTranscripts(anyList())).thenReturn(reply);
        when(gateway.readExamImage(eq("image/png"),any(byte[].class))).thenReturn("fixture table");
        mvc.perform(get(endpoint+"/preview").session(session)).andExpect(status().isOk())
            .andExpect(jsonPath("$.data.local_document").value(true))
            .andExpect(jsonPath("$.data.page_ocr").value(true));
        Map<String,Object> body = map("workspace",vault.root().toString(),"revision",saved.path("revision").asText(),
            "evidence_mode","mirobody_local","consent",false);
        mvc.perform(post(endpoint+"/analysis").session(session).header("X-CSRF-Token",csrf)
            .contentType("application/json").content(json.writeValueAsString(body))).andExpect(status().isOk())
            .andExpect(jsonPath("$.data.analysis_version").value(5))
            .andExpect(jsonPath("$.data.findings.metrics[0].status").value("abnormal"))
            .andExpect(jsonPath("$.data.findings.pdfPageEvidenceVerified").value(true));
        body.put("evidence_mode","mirobody_ocr");
        mvc.perform(post(endpoint+"/analysis").session(session).header("X-CSRF-Token",csrf)
            .contentType("application/json").content(json.writeValueAsString(body))).andExpect(status().isUnprocessableEntity());
        verify(gateway,never()).readExamImage(anyString(),any(byte[].class));
        body.put("consent",true);
        mvc.perform(post(endpoint+"/analysis").session(session).header("X-CSRF-Token",csrf)
            .contentType("application/json").content(json.writeValueAsString(body))).andExpect(status().isOk())
            .andExpect(jsonPath("$.data.analysis_version").value(6))
            .andExpect(jsonPath("$.data.findings.textEvidenceVerified").value(false))
            .andExpect(jsonPath("$.data.previous_report_path").isNotEmpty());
        mvc.perform(get("/api/exams/timeline").session(session)).andExpect(status().isOk())
            .andExpect(jsonPath("$.data.verified_report_count").value(1))
            .andExpect(jsonPath("$.data.individual_metrics[0].page_verified").value(true));
        verify(gateway).readExamImage(eq("image/png"),any(byte[].class));
        verify(gateway,never()).completeExam(anyString(),anyString());
        verifyNoInteractions(files);
    }

    @Test void standardCodesConnectRenamedCompatibleMeasurementsWithOriginalValues() throws Exception {
        Map<String,Object> old = classificationMetric("TEST_NAME_A","14","g/dL","12-16","","TEST_NAME_A 14 g/dL 12-16");
        Map<String,Object> recent = classificationMetric("TEST_NAME_B","143","g/L","120-160","","TEST_NAME_B 143 g/L 120-160");
        timelineExam("2020-01-01",true,Collections.singletonList(old),"");
        timelineExam("2021-01-01",true,Collections.singletonList(recent),"");
        doAnswer(invocation -> {
            List<JsonNode> findings = invocation.getArgument(0);
            for (JsonNode report : findings) for (JsonNode metric : report.path("metrics")) {
                ((com.fasterxml.jackson.databind.node.ObjectNode)metric).set("standardization",json.valueToTree(map(
                    "state","coded","loinc","718-7","comparison_unit","g/L","comparison_value",metric.path("name").asText().endsWith("A") ? "140" : "143")));
            }
            return null;
        }).when(engine).annotate(anyList());
        mvc.perform(get("/api/exams/timeline").session(session)).andExpect(status().isOk())
            .andExpect(jsonPath("$.data.metrics[0].loinc").value("718-7"))
            .andExpect(jsonPath("$.data.metrics[0].converted").value(true))
            .andExpect(jsonPath("$.data.metrics[0].change").value("3"))
            .andExpect(jsonPath("$.data.metrics[0].points[0].value").value("14"))
            .andExpect(jsonPath("$.data.metrics[0].points[0].unit").value("g/dL"));
    }

    private Map<String,Object> timelineMetric(String name,String value,String unit) {
        return map("name",name,"value",value,"unit",unit,"range","38-45","flag","","location","第 2 页",
            "quote",name + " " + value + " " + unit + " 38-45");
    }

    @Test void classifiesHistoricalAndSingleExamMetricsFromEachReportsOwnEvidence() throws Exception {
        Map<String,Object> older = classificationMetric("ALT","40","U/L","≤40", "", "ALT 40 U/L ≤40");
        Map<String,Object> later = classificationMetric("ALT","40","U/L","<40", "", "ALT 40 U/L <40");
        Map<String,Object> once = classificationMetric("TEST_ONCE","12","U/L","1-20", "H", "TEST_ONCE 12 U/L 1-20 H");
        Map<String,Object> unitOnly = classificationMetric("构造无标记","12","U/L","", "L", "构造无标记 12 U/L");
        Map<String,Object> qualitative = classificationMetric("TEST_QUALITATIVE","阴性","","阴性", "", "TEST_QUALITATIVE 阴性 阴性");
        timelineExam("2023-02-18", true, Collections.singletonList(older), "");
        String id = timelineExam("2024-02-18", true, Arrays.asList(later,once,unitOnly,qualitative), "");

        mvc.perform(get("/api/exams/"+id).session(session)).andExpect(status().isOk())
            .andExpect(jsonPath("$.data.findings.metrics[0].status").value("abnormal"))
            .andExpect(jsonPath("$.data.findings.metrics[0].flag").value(""))
            .andExpect(jsonPath("$.data.findings.metrics[1].status").value("abnormal"))
            .andExpect(jsonPath("$.data.findings.metrics[2].status").value("unknown"))
            .andExpect(jsonPath("$.data.findings.metrics[3].status").value("normal"));
        mvc.perform(get("/api/exams/timeline").session(session)).andExpect(status().isOk())
            .andExpect(jsonPath("$.data.metrics[0].status").value("abnormal"))
            .andExpect(jsonPath("$.data.metrics[0].points[0].status").value("normal"))
            .andExpect(jsonPath("$.data.metrics[0].points[1].status").value("abnormal"))
            .andExpect(jsonPath("$.data.metrics[0].flagged_count").value(0))
            .andExpect(jsonPath("$.data.individual_metrics[0].name").value("TEST_ONCE"))
            .andExpect(jsonPath("$.data.individual_metrics[0].status").value("abnormal"))
            .andExpect(jsonPath("$.data.individual_metrics[1].name").value("TEST_QUALITATIVE"))
            .andExpect(jsonPath("$.data.individual_metrics[1].status").value("normal"));
        verifyNoInteractions(files,gateway);
    }

    private Map<String,Object> classificationMetric(String name, String value, String unit, String range, String flag, String quote) {
        return map("name",name,"value",value,"unit",unit,"range",range,"flag",flag,"quote",quote,"location","第 2 页");
    }

    @Test void publicReferencesFillDisplayGapsWithoutReplacingOriginalRangesOrFlags() throws Exception {
        Map<String,Object> bmi = map("name","BMI","value","22.0","unit","kg/m²","range","","flag","",
            "quote","BMI 22.0 kg/m²","location","第 1 页");
        Map<String,Object> egfr = map("name","eGFR(CKD-EPI)","value","111.1","unit",">90mL/min/1.73m^2","range","","flag","",
            "quote","eGFR(CKD-EPI) 111.1 >90mL/min/1.73m^2","location","第 9 页");
        Map<String,Object> bloodPressure = map("name","血压","value","124/78","unit","mmHg","range","","flag","",
            "quote","血压 124/78 mmHg","location","第 2 页");
        Map<String,Object> unrelated = map("name","构造未知项目","value","2.1","unit","U/L","range","","flag","",
            "quote","构造未知项目 2.1 U/L","location","第 2 页","external_reference",map("source_url","https://test.invalid"));
        String id = timelineExam("2022-05-11",true,Arrays.asList(bmi,egfr,bloodPressure,unrelated),"");
        Map<String,Object> later = map("name","BMI","value","22.3","unit","kg/m²","range","19–23","flag","",
            "quote","BMI 22.3 kg/m² 19–23","location","第 3 页");
        String newer = timelineExam("2023-06-12",true,Collections.singletonList(later),"");
        mvc.perform(get("/api/exams/"+id).session(session)).andExpect(status().isOk())
            .andExpect(jsonPath("$.data.findings.metrics[0].range").value(""))
            .andExpect(jsonPath("$.data.findings.metrics[0].flag").value(""))
            .andExpect(jsonPath("$.data.findings.metrics[0].status").value("unknown"))
            .andExpect(jsonPath("$.data.findings.metrics[0].external_reference.display_range").value("18.5 ≤ BMI < 24.0 kg/m²"))
            .andExpect(jsonPath("$.data.findings.metrics[0].external_reference.source_url").value(
                "https://www.nhc.gov.cn/wjw/ylyjs/202412/b3d40e0141834897808ce6c9dce76a60/files/1736390749000_59785.pdf"))
            .andExpect(jsonPath("$.data.findings.metrics[1].unit").value("mL/min/1.73m^2"))
            .andExpect(jsonPath("$.data.findings.metrics[1].range").value(">90"))
            .andExpect(jsonPath("$.data.findings.metrics[1].range_recovered").value(true))
            .andExpect(jsonPath("$.data.findings.metrics[1].status").value("normal"))
            .andExpect(jsonPath("$.data.findings.metrics[1].external_reference").doesNotExist())
            .andExpect(jsonPath("$.data.findings.metrics[2].external_reference.source_url").value("https://pmc.ncbi.nlm.nih.gov/articles/PMC11937835/"))
            .andExpect(jsonPath("$.data.findings.metrics[3].external_reference").doesNotExist());
        mvc.perform(get("/api/exams/"+newer).session(session)).andExpect(status().isOk())
            .andExpect(jsonPath("$.data.findings.metrics[0].external_reference").doesNotExist())
            .andExpect(jsonPath("$.data.findings.metrics[0].range").value("19–23"));
        mvc.perform(get("/api/exams/timeline").session(session)).andExpect(status().isOk())
            .andExpect(jsonPath("$.data.metrics[0].status").value("unknown"))
            .andExpect(jsonPath("$.data.metrics[0].points[0].external_reference.display_range").value("18.5 ≤ BMI < 24.0 kg/m²"))
            .andExpect(jsonPath("$.data.metrics[0].points[0].external_reference.applies_to").isNotEmpty())
            .andExpect(jsonPath("$.data.metrics[0].points[1].external_reference").doesNotExist())
            .andExpect(jsonPath("$.data.metrics[0].points[1].range").value("19–23"));
        verifyNoInteractions(files,gateway);
    }

    private String timelineExam(String date, boolean verified, List<Map<String,Object>> metrics, String observation) throws Exception {
        org.springframework.mock.web.MockMultipartFile file = new org.springframework.mock.web.MockMultipartFile(
            "file","fixture.txt","text/plain","构造追踪报告".getBytes(StandardCharsets.UTF_8));
        JsonNode exam = utf8(mvc.perform(multipart("/api/exams").file(file).session(session).header("X-CSRF-Token",csrf)
            .param("workspace",vault.root().toString()).param("date",date).param("mode","archive"))
            .andExpect(status().isOk()).andReturn());
        String id = exam.path("id").asText(), revision = exam.path("revision").asText();
        String findings = json.writeValueAsString(map("metrics",metrics,"textEvidenceVerified",verified,"pdfPageEvidenceVerified",verified,
            "observations",observation.isEmpty() ? Collections.emptyList() : Collections.singletonList(map("quote",observation,"location","第 3 页"))));
        vault.saveReport("体检/" + id + "-" + revision + "-v3","---\ndomain: analysis\nrecord_type: exam_analysis\n"
            + "source_revision: " + revision + "\nfindings: " + findings + "\n---\n");
        return id;
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
}
