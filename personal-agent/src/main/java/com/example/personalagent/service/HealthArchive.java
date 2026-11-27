package com.example.personalagent.service;

import com.example.personalagent.model.VaultNote;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;
import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.StandardCharsets;
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
    private static final int ANALYSIS_VERSION = 3;
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
        String importId = fields.getOrDefault("import_id", "");
        require(importId.isEmpty() || (!analyze
            && importId.matches("[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")), "归档编号无效");
        require(date.matches("\\d{4}-\\d{2}-\\d{2}"), "请填写报告上的检查日期");
        try { LocalDate.parse(date); } catch (java.time.DateTimeException invalid) { require(false, "检查日期无效"); }
        Attachment document = new Attachment(file);
        String key = importId.isEmpty() ? id() : importId;
        String path = SOURCES + key + ".md", attachment = ORIGINALS + key + "." + document.storageExtension();
        String note = "---\ntitle: 体检记录 · " + date + "\ndomain: health\nrecord_type: exam_source\nstatus: historical"
            + "\nsource: 体检原件\nobserved_at: \"" + date + "\"\nrecorded_at: \"" + now() + "\"\nai_exclude: true"
            + "\nattachment: " + attachment + "\nattachment_sha256: " + document.hash
            + "\n---\n\n[[" + attachment + "|体检原件]]\n";
        VaultNote saved;
        synchronized (vault) {
            documents.checkWorkspace(workspace);
            if (!importId.isEmpty() && Files.isRegularFile(vault.safe(path))) {
                // 响应丢失后允许重试同一文件，防止生成重复记录或覆盖其他原件。
                saved = source(key);
                if (!date.equals(saved.properties.get("observed_at"))
                    || !document.hash.equals(saved.properties.get("attachment_sha256"))
                    || !attachment.equals(saved.properties.get("attachment"))) {
                    throw conflict("此归档编号已用于另一份记录，请返回健康档案核对");
                }
                documents.original(saved, ORIGINALS, key);
            } else {
                saved = documents.save(document, workspace, path, attachment, note);
            }
        }
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
                exams.add(map("id", key, "date", note.properties.get("observed_at"), "title", note.title,
                    "ready", existingVersion(key,note) != 0));
            }
            exams.sort(Comparator.comparing((Map<String,Object> item) -> text(item,"date")).reversed());
            return map("reports",exams,"workspace",vault.root().toString());
        }
    }

    public Object detail(String key) throws Exception {
        synchronized (vault) {
            VaultNote source = source(key);
            int version = existingVersion(key,source);
            String report = version == 0 ? null : reportPath(key,source,version);
            int previous = version == ANALYSIS_VERSION ? previousVersion(key,source) : 0;
            return map("id",key,"title",source.title,"date",source.properties.get("observed_at"),"source_path",source.path,"revision",source.revision,
                "transcript",reviewedText(source),"report_path",report,
                "analysis_version",version,"previous_report_path",previous == 0 ? null : reportPath(key,source,previous),
                "findings",report == null ? null : vault.read(report).properties.get("findings"));
        }
    }

    public Object preview(String key) throws Exception {
        Attachment document;
        synchronized (vault) {
            VaultNote source = source(key);
            document = new Attachment(documents.original(source, ORIGINALS, key));
            if (!document.hash.equals(source.properties.get("attachment_sha256"))) throw conflict("原件已变化，请在 Obsidian 核实");
        }
        return ExamPdfText.inspect(document).preview();
    }

    public Object analyze(String key, Map<String,Object> input) throws Exception {
        require(Boolean.TRUE.equals(input.get("consent")), "请先确认把体检原件发送给所选模型");
        if (!analyzing.tryAcquire()) throw conflict("已有健康分析正在进行，请稍后刷新");
        try {
            VaultNote source; Path workspace; Attachment document; String report;
            synchronized (vault) {
                documents.checkWorkspace(text(input,"workspace"));
                source = source(key); workspace = vault.root();
                if (!source.revision.equals(input.get("revision"))) throw conflict("来源已变化，请刷新后重新确认");
                report = reportPath(key,source,ANALYSIS_VERSION);
                if (Files.isRegularFile(vault.safe(report))) {
                    if (!validReport(report,source)) throw conflict("体检分析草稿路径已被其他内容占用，请先备份并移走该文件后重试");
                    return detail(key);
                }
                document = new Attachment(documents.original(source, ORIGINALS, key));
                if (!document.hash.equals(source.properties.get("attachment_sha256"))) throw conflict("原件已变化，请在 Obsidian 核实");
            }
            ExamPdfText pdf = ExamPdfText.inspect(document);
            require(!"unavailable".equals(pdf.mode), pdf.message);
            String approvedMode = text(input,"evidence_mode");
            boolean useOriginalPdf = "original".equals(approvedMode) && "pdf_text".equals(pdf.mode);
            if (!approvedMode.isEmpty() && !approvedMode.equals(pdf.mode) && !useOriginalPdf) {
                throw conflict("可用的原件解析方式已变化，请重新打开这份报告并确认");
            }
            boolean localPdf = "pdf_text".equals(pdf.mode) && !useOriginalPdf;
            String answer = localPdf ? documents.analyzeExtractedText(pdf.modelInput(), ExamFindings.INSTRUCTIONS
                + "用户消息为本机提取的 PDF 文字，按 [第 N 页] 标注实际页码。引用同一页的连续文字，不将页码标签放进摘录。")
                : documents.analyze(document, ExamFindings.INSTRUCTIONS);
            ExamFindings findings;
            try {
                findings = ExamFindings.parse(json, answer);
                String text = utf8Evidence(document);
                if (localPdf) findings.verifyPdfEvidence(pdf.pages);
                else if (text != null) findings.verifyTextEvidence(text);
            }
            catch (java.io.IOException invalid) { throw new ResponseStatusException(HttpStatus.BAD_GATEWAY,"模型输出格式不完整或摘录无法与原件匹配。原件已保存，可更换模型后重试。"); }
            synchronized (vault) {
                if (!vault.root().equals(workspace) || !source(key).revision.equals(source.revision)) throw conflict("仓库或报告已变化，未写入分析，请重新核对");
                if (Files.isRegularFile(vault.safe(report))) throw conflict("体检分析草稿路径已被其他内容占用，请先备份并移走该文件后重试");
                // 确认上传后到写入草稿之间，原件仍与归档哈希一致。
                documents.original(source, ORIGINALS, key);
                String date = String.valueOf(source.properties.get("observed_at"));
                StringBuilder markdown = new StringBuilder("---\ndomain: analysis\nrecord_type: exam_analysis\norigin: ai_generated\nstatus: draft\nai_exclude: true\ntitle: ")
                    .append(json.writeValueAsString("体检解读 · " + date)).append("\nrecorded_at: \"").append(now()).append("\"\nsource_revision: ").append(source.revision)
                    .append("\nfindings: ").append(json.writeValueAsString(findings)).append("\n---\n\n> AI 草稿，仅解释本次报告，不替代医生诊断。\n\n## 本次概览\n\n")
                    .append(indent(findings.summary)).append("\n\n");
                appendEvidence(markdown, "原报告建议", findings.recommendations);
                appendEvidence(markdown, "重点发现", findings.observations);
                if (!findings.questions.isEmpty()) {
                    markdown.append("## 就医沟通\n\n");
                    for (String question : findings.questions) markdown.append(indent(question)).append("\n\n");
                }
                if (!findings.limitations.isEmpty()) {
                    markdown.append("## 资料局限\n\n");
                    for (String limitation : findings.limitations) markdown.append(indent(limitation)).append("\n\n");
                }
                markdown.append("## 指标与原文\n\n");
                for (Map<String,String> metric : findings.metrics) markdown.append(indent(metric.get("name") + "：" + metric.get("value") + " " + metric.get("unit")
                    + "  参考：" + metric.get("range") + "  标记：" + metric.get("flag") + "\n摘录：" + metric.get("quote")
                    + "\n位置：" + metric.get("location"))).append("\n\n");
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
    private int existingVersion(String key, VaultNote note) throws Exception {
        return validReport(reportPath(key,note,ANALYSIS_VERSION),note) ? ANALYSIS_VERSION : previousVersion(key,note);
    }

    private int previousVersion(String key, VaultNote note) throws Exception {
        if (validReport(reportPath(key,note,2),note)) return 2;
        return Files.isRegularFile(vault.safe(reportPath(key,note,1))) ? 1 : 0;
    }

    private boolean validReport(String path, VaultNote note) throws Exception {
        if (!Files.isRegularFile(vault.safe(path))) return false;
        try {
            // 仅展示当前来源版本生成的草稿，忽略占用路径的外来文件。
            VaultNote report = vault.read(path);
            return "exam_analysis".equals(report.properties.get("record_type"))
                && Objects.equals(note.revision, String.valueOf(report.properties.get("source_revision")));
        } catch (Exception unreadable) {
            return false;
        }
    }

    private static String reportPath(String key, VaultNote note, int version) {
        return REPORTS + key + "-" + note.revision + (version == 1 ? "" : "-v" + version) + ".md";
    }

    private static String utf8Evidence(Attachment document) {
        if (!textLike(document.extension)) return null;
        try {
            return StandardCharsets.UTF_8.newDecoder().decode(ByteBuffer.wrap(document.bytes)).toString();
        } catch (CharacterCodingException unsupportedEncoding) {
            // 不猜测旧文本的字符编码，保留草稿让用户回查原件。
            return null;
        }
    }

    private static void appendEvidence(StringBuilder markdown, String heading, List<Map<String,String>> entries) {
        if (entries.isEmpty()) return;
        markdown.append("## ").append(heading).append("\n\n");
        for (Map<String,String> entry : entries) {
            markdown.append(indent("原件摘录：" + entry.get("quote") + "\n位置：" + entry.get("location"))).append("\n\n");
            if (entry.containsKey("interpretation")) {
                markdown.append(indent("AI 解读：" + entry.get("interpretation"))).append("\n\n");
            }
        }
    }
}
