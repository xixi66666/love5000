package com.example.personalagent.service;

import com.example.personalagent.model.VaultNote;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;
import java.nio.file.*;
import java.time.LocalDate;
import java.util.*;
import java.util.concurrent.Semaphore;
import static com.example.personalagent.Api.*;
import static com.example.personalagent.service.LocalDocuments.*;

@Service
public class HealthArchive {
    static final String SOURCES = "30-健康/体检/", ORIGINALS = "99-附件/体检/";
    private static final String REPORTS = "80-AI分析/体检/";
    private final VaultService vault;
    private final ObjectMapper json;
    private final LocalDocuments documents;
    private final Semaphore analyzing = new Semaphore(1);

    public HealthArchive(VaultService vault, ObjectMapper json, LocalDocuments documents) {
        this.vault = vault; this.json = json; this.documents = documents;
    }

    public Object archive(MultipartFile file, Map<String,String> fields) throws Exception {
        boolean analyze = wantsAnalysis(fields);
        String date = fields.getOrDefault("date", ""), workspace = fields.get("workspace");
        require(date.matches("\\d{4}-\\d{2}-\\d{2}"), "请填写报告上的检查日期");
        try { LocalDate.parse(date); } catch (java.time.DateTimeException invalid) { require(false, "检查日期无效"); }
        Attachment document = new Attachment(file);
        String key = id(), path = SOURCES + key + ".md", attachment = ORIGINALS + key + "." + document.storageExtension();
        String note = "---\ntitle: 体检记录 · " + date + "\ndomain: health\nrecord_type: exam_source\nstatus: historical"
            + "\nsource: 体检原件\nobserved_at: \"" + date + "\"\nrecorded_at: \"" + now() + "\"\nai_exclude: true"
            + "\nattachment: " + attachment + "\nattachment_sha256: " + document.hash
            + "\n---\n\n[[" + attachment + "|体检原件]]\n";
        VaultNote saved = documents.save(document, workspace, path, attachment, note);
        Map<String,Object> result = map("id", key, "revision", saved.revision, "path", path);
        if (analyze) {
            try { analyze(key, map("consent",true,"revision",saved.revision,"workspace",workspace)); }
            catch (ResponseStatusException failure) { result.put("warning", failure.getReason()); }
        }
        return result;
    }

    public Object overview() throws Exception {
        synchronized (vault) {
            List<Map<String,Object>> exams = new ArrayList<>();
            for (VaultNote note : vault.notes()) {
                if (!note.path.matches(SOURCES + "[0-9a-f-]{36}\\.md") || !"exam_source".equals(note.properties.get("record_type"))) continue;
                String key = note.path.substring(SOURCES.length(), note.path.length()-3);
                exams.add(map("id", key, "date", note.properties.get("observed_at"), "title", note.title, "ready", Files.isRegularFile(vault.safe(reportPath(key,note)))));
            }
            exams.sort(Comparator.comparing((Map<String,Object> item) -> text(item,"date")).reversed());
            return map("reports",exams,"workspace",vault.root().toString());
        }
    }

    public Object detail(String key) throws Exception {
        synchronized (vault) {
            VaultNote source = source(key); String report = reportPath(key,source);
            boolean ready = Files.isRegularFile(vault.safe(report));
            return map("id",key,"title",source.title,"date",source.properties.get("observed_at"),"source_path",source.path,"revision",source.revision,
                "transcript",reviewedText(source),"report_path",ready ? report : null,
                "findings",ready ? vault.read(report).properties.get("findings") : null);
        }
    }

    public Object analyze(String key, Map<String,Object> input) throws Exception {
        require(Boolean.TRUE.equals(input.get("consent")), "请先确认把体检原件发送给 DeepSeek");
        if (!analyzing.tryAcquire()) throw conflict("已有健康分析正在进行，请稍后刷新");
        try {
            VaultNote source; Path workspace; Attachment document; String report;
            synchronized (vault) {
                documents.checkWorkspace(text(input,"workspace"));
                source = source(key); workspace = vault.root();
                if (!source.revision.equals(input.get("revision"))) throw conflict("来源已变化，请刷新后重新确认");
                report = reportPath(key,source);
                if (Files.isRegularFile(vault.safe(report))) return detail(key);
                document = new Attachment(documents.original(source, ORIGINALS, key));
                if (!document.hash.equals(source.properties.get("attachment_sha256"))) throw conflict("原件已变化，请在 Obsidian 核实");
            }
            String answer = documents.analyze(document, ExamFindings.INSTRUCTIONS);
            ExamFindings findings;
            try { findings = ExamFindings.parse(json, answer); }
            catch (java.io.IOException invalid) { throw new ResponseStatusException(HttpStatus.BAD_GATEWAY,"模型未返回可用的体检草稿，请核对原件后重试"); }
            synchronized (vault) {
                if (!vault.root().equals(workspace) || !source(key).revision.equals(source.revision)) throw conflict("仓库或报告已变化，未写入分析，请重新核对");
                String date = String.valueOf(source.properties.get("observed_at"));
                StringBuilder markdown = new StringBuilder("---\ndomain: analysis\nrecord_type: exam_analysis\norigin: ai_generated\nstatus: draft\nai_exclude: true\ntitle: ")
                    .append(json.writeValueAsString("体检解读 · " + date)).append("\nrecorded_at: \"").append(now()).append("\"\nsource_revision: ").append(source.revision)
                    .append("\nfindings: ").append(json.writeValueAsString(findings)).append("\n---\n\n> AI 草稿，仅解释本次报告，不替代医生诊断。\n\n## 本次概览\n\n")
                    .append(indent(findings.summary)).append("\n\n## 指标与原文\n\n");
                for (Map<String,String> metric : findings.metrics) markdown.append(indent(metric.get("name") + "：" + metric.get("value") + " " + metric.get("unit")
                    + "  参考：" + metric.get("range") + "  标记：" + metric.get("flag") + "\n摘录：" + metric.get("quote")
                    + "\n位置：" + metric.get("location"))).append("\n\n");
                markdown.append("## 就医沟通\n\n");
                for (String question : findings.questions) markdown.append(indent(question)).append("\n\n");
                markdown.append("## 来源\n\n[[").append(source.path).append("|体检记录]] · 来源 SHA-256 `").append(source.revision)
                    .append("` · 原件 SHA-256 `").append(document.hash).append("`\n");
                vault.saveReport(report.substring("80-AI分析/".length(),report.length()-3),markdown.toString());
                return detail(key);
            }
        } finally { analyzing.release(); }
    }

    public boolean busy() { return analyzing.availablePermits() == 0; }

    public Path original(String key) throws Exception {
        synchronized (vault) {
            return documents.original(source(key), ORIGINALS, key);
        }
    }
    private VaultNote source(String key) throws Exception {
        require(key.matches("[0-9a-f-]{36}"), "体检记录编号无效");
        VaultNote note = vault.read(SOURCES + key + ".md");
        require("exam_source".equals(note.properties.get("record_type")), "不是体检报告来源"); return note;
    }
    private static String reportPath(String key, VaultNote note) { return REPORTS + key + "-" + note.revision + ".md"; }
}
