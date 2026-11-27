package com.example.personalagent.service;

import com.example.personalagent.model.VaultNote;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.time.LocalDate;
import java.util.*;
import java.util.concurrent.Semaphore;
import static com.example.personalagent.Api.*;
import static com.example.personalagent.service.LocalDocuments.*;

/**
 * 健康档案：体检原件的归档、预览、AI 解读与版本管理。
 *
 * <p>属服务层，关键协作者：{@link VaultService}（受约束的读写与资料指纹）、
 * {@link LocalDocuments}（附件校验、哈希与模型调用）、{@link ExamPdfText}
 * （本机 PDF 文字层提取）、{@link DeepSeekFiles}（完整原件识别）。</p>
 *
 * <p>磁盘布局固定三处：来源笔记 {@code 30-健康/体检/<id>.md}、原件
 * {@code 99-附件/体检/<id>.<ext>}、解读草稿
 * {@code 80-AI分析/体检/<id>-<来源revision>[-vN].md}。草稿文件名带来源哈希，因此来源被
 * 编辑后旧草稿自然失效而不会被当现状展示；本机表格、分页识别、增强 AI 解读分别使用 v5、v6、v7，旧版路径继续可读以兼容
 * 既有资料。</p>
 *
 * <p>并发与失败语义：{@link Semaphore} 保证同一时刻只有一次解读；原件哈希在归档、
 * 预览、解读前后各比对一次，外部改动时报 409 而不是用错内容去解读。归档时的
 * {@code import_id} 重试必须与既有记录完全一致（日期、原件哈希、附件路径），
 * 否则拒绝，避免批量导入因响应丢失而写出重复记录。</p>
 */
@Service
public class HealthArchive {
    // SOURCES 存来源笔记、ORIGINALS 存原件；原件目录被 Quartz 构建排除，来源笔记靠 ai_exclude 不进 AI 检索。
    static final String SOURCES = ExamPaths.SOURCES, ORIGINALS = ExamPaths.ORIGINALS;
    /** 草稿目录与当前解读版本号；v3 起摘录必须与原件文字逐字匹配，旧版路径仍可读。 */
    private static final String REPORTS = ExamPaths.REPORTS;
    private static final int LEGACY_VERSION = 4, DOCUMENT_VERSION = 5, OCR_VERSION = 6, ENRICHED_VERSION = 7;
    private final VaultService vault;
    private final ObjectMapper json;
    private final LocalDocuments documents;
    private final MirobodyEngine engine;
    private final ExamDocumentAnalysis documentAnalysis;
    /** 解读信号量：非公平但只允许一份解读在跑，第二次并发请求立即以 409 失败而不是排队。 */
    private final Semaphore analyzing = new Semaphore(1);

    public HealthArchive(VaultService vault, ObjectMapper json, LocalDocuments documents, MirobodyEngine engine, ExamDocumentAnalysis documentAnalysis) {
        this.vault = vault; this.json = json; this.documents = documents;
        this.engine = engine; this.documentAnalysis = documentAnalysis;
    }

    /**
     * 归档一份体检原件，可选地立即解读。
     *
     * <p>写入顺序是「先原件、后笔记」，两步都在 {@code vault} 监视器内完成。
     * {@code import_id} 已存在时走幂等分支：日期、原件哈希、附件路径三者必须与既有记录
     * 一致，否则 409。解读失败只回写 {@code warning}，不撤销已归档的原件——原件才是
     * 用户真正上传的东西。</p>
     *
     * @param file   原件，最大 12 MB，后缀白名单见 {@link LocalDocuments}
     * @param fields {@code date}（必填，{@code yyyy-MM-dd}）与 {@code workspace}，
     *               可选 {@code mode}、{@code consent}、{@code import_id}
     * @return {@code id/revision/path}，解读失败时追加 {@code warning}
     * @throws Exception 日期非法、编号格式不符、与既有记录冲突或写盘失败时抛出
     */
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

    /**
     * 列出全部体检来源，按检查日期倒序。
     *
     * @return {@code reports} 与当前仓库路径；每项含 {@code id/date/title/ready}，
     *         {@code ready} 表示已存在与当前来源版本匹配的草稿
     */
    public Object overview() throws Exception {
        synchronized (vault) {
            List<Map<String,Object>> exams = new ArrayList<>();
            for (VaultNote note : examSources()) {
                String key = examId(note);
                exams.add(map("id", key, "date", note.properties.get("observed_at"), "title", note.title,
                    "ready", existingVersion(key,note) != 0));
            }
            exams.sort(Comparator.comparing((Map<String,Object> item) -> text(item,"date")).reversed());
            return map("reports",exams,"workspace",vault.root().toString());
        }
    }

    /** 关联由当前 Vault 中的证据生成，读取时无需调用模型或写入笔记。 */
    public Object timeline() throws Exception {
        List<TimelineSource> sources = new ArrayList<>();
        synchronized (vault) {
            for (VaultNote note : examSources()) {
                if (Arrays.asList("archived","corrected").contains(note.properties.get("status"))) continue;
                String id = examId(note);
                int version = existingVersion(id,note);
                JsonNode findings = metricDetails(version == 0 ? null : vault.read(reportPath(id,note,version)).properties.get("findings"));
                // OCR 或整件识别稿可以作为当前阅读版本，历年关联继续使用最近有已核对证据的草稿。
                while (!findings.path("textEvidenceVerified").asBoolean() && version > LEGACY_VERSION) {
                    version = availableVersion(id,note,version - 1);
                    findings = metricDetails(version == 0 ? null : vault.read(reportPath(id,note,version)).properties.get("findings"));
                }
                sources.add(new TimelineSource(id,Objects.toString(note.properties.get("observed_at"),""),note.path,findings));
            }
        }
        List<JsonNode> findings = new ArrayList<>();
        sources.forEach(source -> findings.add(source.findings));
        engine.annotate(findings);
        ExamTimeline timeline = new ExamTimeline();
        sources.forEach(source -> timeline.add(source.id,source.date,source.path,source.findings));
        return timeline.result();
    }

    private static final class TimelineSource {
        final String id, date, path;
        final JsonNode findings;
        TimelineSource(String id, String date, String path, JsonNode findings) {
            this.id = id; this.date = date; this.path = path; this.findings = findings;
        }
    }

    private List<VaultNote> examSources() throws Exception {
        Path directory = vault.safe(SOURCES);
        if (!Files.isDirectory(directory)) return Collections.emptyList();
        List<VaultNote> notes = new ArrayList<>();
        try (DirectoryStream<Path> entries = Files.newDirectoryStream(directory,"*.md")) {
            for (Path entry : entries) {
                String filename = entry.getFileName().toString();
                if (!filename.matches("[0-9a-f-]{36}\\.md") || !Files.isRegularFile(entry,LinkOption.NOFOLLOW_LINKS)) continue;
                VaultNote note = vault.read(SOURCES+filename);
                if ("exam_source".equals(note.properties.get("record_type"))) notes.add(note);
            }
        }
        return notes;
    }

    private JsonNode metricDetails(Object findings) {
        JsonNode details = ExamMetricStatus.annotate(ExamMetricReferences.annotate(json,findings));
        for (JsonNode row : details.path("metrics")) {
            if (row.isObject()) ((ObjectNode) row).remove("standardization");
        }
        return details;
    }

    private static String examId(VaultNote note) {
        return note.path.substring(SOURCES.length(), note.path.length()-3);
    }

    /**
     * 单份体检的详情。
     *
     * @param key 体检记录编号（UUID）
     * @return 来源信息、已核对文字、当前草稿路径与版本、上一版草稿路径及解析出的发现；
     *         没有草稿时 {@code report_path} 与 {@code findings} 为 {@code null}
     */
    public Object detail(String key) throws Exception {
        Map<String,Object> detail;
        JsonNode findings;
        synchronized (vault) {
            VaultNote source = source(key);
            int version = existingVersion(key,source);
            String report = version == 0 ? null : reportPath(key,source,version);
            int previous = version > 1 ? availableVersion(key,source,version - 1) : 0;
            findings = report == null ? null : metricDetails(vault.read(report).properties.get("findings"));
            detail = map("id",key,"title",source.title,"date",source.properties.get("observed_at"),"source_path",source.path,"revision",source.revision,
                "transcript",reviewedText(source),"report_path",report,
                "analysis_version",version,"latest_analysis_version",Math.max(version,engine.available() ? ENRICHED_VERSION : LEGACY_VERSION),
                "previous_report_path",previous == 0 ? null : reportPath(key,source,previous),
                "findings",findings);
        }
        if (findings != null) engine.annotate(Collections.singletonList(findings));
        return detail;
    }

    /**
     * 在本机提取原件文字层，返回只读预览；不调用任何外部模型。
     *
     * @param key 体检记录编号
     * @return 预览结构，{@code mode} 为 {@code pdf_text}（可直接取文字）或
     *         {@code original}（需整份上传）
     * @throws Exception 原件被移动，或哈希与归档时不一致时抛出 409
     */
    public Object preview(String key) throws Exception {
        Attachment document;
        synchronized (vault) {
            VaultNote source = source(key);
            document = new Attachment(documents.original(source, ORIGINALS, key));
            if (!document.hash.equals(source.properties.get("attachment_sha256"))) throw conflict("原件已变化，请在 Obsidian 核实");
        }
        ExamPdfText pdf = ExamPdfText.inspect(document);
        Map<String,Object> preview = pdf.preview();
        boolean permitted = !"unavailable".equals(pdf.mode);
        preview.put("local_document",permitted && documentAnalysis.canParseLocal(document.extension));
        preview.put("page_ocr",permitted && documentAnalysis.canUseOcr(document.extension,pdf));
        preview.put("is_pdf","pdf".equals(document.extension));
        return preview;
    }

    /**
     * 生成或读取当前版本的体检解读草稿。
     *
     * <p>整个方法被信号量串行化：已有一份解读在跑时返回 409。目标草稿路径已存在且来源
     * 匹配时直接返回详情（幂等）；路径被来源不匹配的外来文件占用则 409，绝不覆盖。
     * 证据路径有三种：{@code pdf_text} 用本机提取的文字、{@code original} 允许把整份 PDF
     * 交给模型、其余情况按扩展名走文件识别。模型输出必须先通过 {@link ExamFindings}
     * 的摘录校验，否则 502 且不写草稿，原件保持可用。</p>
     *
     * @param key   体检记录编号
     * @param input 请求体：{@code consent=true}、来源 {@code revision}、{@code workspace}，
     *              可选 {@code evidence_mode}
     * @return 写入后的详情，{@code analysis_version} 为当前版本
     * @throws Exception 未授权、来源已变化、解析方式失效、路径被占用或输出不可核验时抛出
     */
    public Object analyze(String key, Map<String,Object> input) throws Exception {
        String approvedMode = text(input,"evidence_mode");
        boolean localDocument = ExamDocumentAnalysis.LOCAL.equals(approvedMode);
        boolean pageOcr = ExamDocumentAnalysis.OCR.equals(approvedMode);
        boolean structured = localDocument || pageOcr;
        require(localDocument || Boolean.TRUE.equals(input.get("consent")), "请先确认把所选体检内容发送给模型");
        if (!analyzing.tryAcquire()) throw conflict("已有健康分析正在进行，请稍后刷新");
        try {
            VaultNote source; Path workspace; Attachment document; String report;
            synchronized (vault) {
                documents.checkWorkspace(text(input,"workspace"));
                source = source(key); workspace = vault.root();
                if (!source.revision.equals(input.get("revision"))) throw conflict("来源已变化，请刷新后重新确认");
                int version = pageOcr ? OCR_VERSION : localDocument ? DOCUMENT_VERSION : engine.available() ? ENRICHED_VERSION : LEGACY_VERSION;
                report = reportPath(key,source,version);
                if (Files.isRegularFile(vault.safe(report))) {
                    if (!validReport(report,source)) throw conflict("体检分析草稿路径已被其他内容占用，请先备份并移走该文件后重试");
                    return detail(key);
                }
                document = new Attachment(documents.original(source, ORIGINALS, key));
                if (!document.hash.equals(source.properties.get("attachment_sha256"))) throw conflict("原件已变化，请在 Obsidian 核实");
            }
            ExamPdfText pdf = ExamPdfText.inspect(document);
            require(!"unavailable".equals(pdf.mode), pdf.message);
            boolean useOriginalPdf = "original".equals(approvedMode) && "pdf_text".equals(pdf.mode);
            if (!structured && !approvedMode.isEmpty() && !approvedMode.equals(pdf.mode) && !useOriginalPdf) {
                throw conflict("可用的原件解析方式已变化，请重新打开这份报告并确认");
            }
            ExamFindings findings;
            try {
                findings = structured ? documentAnalysis.parse(document,pdf,pageOcr) : analyzeWithModel(document,pdf,useOriginalPdf);
            }
            catch (java.io.IOException invalid) { throw new ResponseStatusException(HttpStatus.BAD_GATEWAY,structured
                ? "文档解析没有完成或证据无法核对。原件已保存，可重试。"
                : "模型输出格式不完整或摘录无法与原件匹配。原件已保存，可更换模型后重试。"); }
            synchronized (vault) {
                if (!vault.root().equals(workspace) || !source(key).revision.equals(source.revision)) throw conflict("仓库或报告已变化，未写入分析，请重新核对");
                if (Files.isRegularFile(vault.safe(report))) throw conflict("体检分析草稿路径已被其他内容占用，请先备份并移走该文件后重试");
                // 确认上传后到写入草稿之间，原件仍与归档哈希一致。
                documents.original(source, ORIGINALS, key);
                String date = String.valueOf(source.properties.get("observed_at"));
                String origin = localDocument ? "local_extraction" : "ai_generated";
                StringBuilder markdown = new StringBuilder("---\ndomain: analysis\nrecord_type: exam_analysis\norigin: ").append(origin)
                    .append("\nstatus: draft\nai_exclude: true\ntitle: ")
                    .append(json.writeValueAsString("体检解读 · " + date)).append("\nrecorded_at: \"").append(now()).append("\"\nsource_revision: ").append(source.revision)
                    .append("\nfindings: ").append(json.writeValueAsString(findings)).append("\n---\n\n> ")
                    .append(localDocument ? "本机提取草稿，请对照体检原件核查。" : "AI 草稿，仅解释本次报告，不替代医生诊断。")
                    .append("\n\n## 本次概览\n\n")
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
                if (findings.omittedEvidence > 0) {
                    markdown.append("另有 ").append(findings.omittedEvidence).append(" 条未通过原件定位或字段校验。\n\n");
                }
                markdown.append("## 指标与原文\n\n");
                for (Map<String,String> metric : findings.metrics) markdown.append(indent(metric.get("name") + "：" + metric.get("value") + " " + metric.get("unit")
                    + "  参考：" + metric.get("range") + "  标记：" + metric.get("flag") + "\n摘录：" + metric.get("quote")
                    + "\n位置：" + metric.get("location"))).append("\n\n");
                markdown.append("## 来源\n\n[[").append(source.path).append("|体检记录]] · 来源 SHA-256 `").append(source.revision)
                    .append("` · 原件 SHA-256 `").append(document.hash).append("`\n");
                vault.saveReport(report.substring("80-AI分析/".length(),report.length()-3),markdown.toString());
            }
            return detail(key);
        } finally { analyzing.release(); }
    }

    private ExamFindings analyzeWithModel(Attachment document, ExamPdfText pdf, boolean useOriginalPdf) throws Exception {
        if ("pdf_text".equals(pdf.mode) && !useOriginalPdf) {
            ExamPdfReferences references = new ExamPdfReferences(pdf.pages);
            ExamFindings draft = references.parse(json,documents.analyzeExtractedText(references.modelInput(),ExamPdfReferences.INSTRUCTIONS));
            if (documentAnalysis.canParseLocal(document.extension)) {
                try {
                    ExamFindings tables = documentAnalysis.parse(document,pdf,false);
                    Set<List<String>> seen = new HashSet<>();
                    tables.metrics.forEach(row -> seen.add(metricKey(row)));
                    draft.metrics.removeIf(row -> seen.contains(metricKey(row)));
                    draft.metrics.addAll(0,tables.metrics);
                    draft.omittedEvidence += tables.omittedEvidence;
                    draft.documentMethod = "mirobody_with_ai";
                    draft.summary = "本机表格和 AI 解读合计收录 " + draft.metrics.size() + " 项指标、"
                        + draft.observations.size() + " 条重点发现和 " + draft.recommendations.size() + " 条原报告建议。";
                } catch (IOException | ResponseStatusException unavailable) {
                    draft.limitations.add("本机表格解析未收录额外指标。本稿依据已定位的原件文字。");
                }
            }
            return draft;
        }
        ExamFindings draft = ExamFindings.parse(json,documents.analyze(document,ExamFindings.INSTRUCTIONS));
        String text = utf8Evidence(document);
        if (text != null) draft.verifyTextEvidence(text);
        return draft;
    }

    private static List<String> metricKey(Map<String,String> metric) {
        return Arrays.asList(metric.get("name"),metric.get("value"),metric.get("unit"),metric.get("location"));
    }

    /** 是否有解读正在进行；切换仓库前由 Controller 用它拦住并发写。 */
    public boolean busy() { return analyzing.availablePermits() == 0; }

    /**
     * 解析并校验体检原件，返回可读文件路径。
     *
     * @throws Exception 记录不存在，或原件哈希与归档时不一致时抛出
     */
    public Path original(String key) throws Exception {
        synchronized (vault) {
            return documents.original(source(key), ORIGINALS, key);
        }
    }
    /**
     * 读取体检来源笔记并确认类型。
     *
     * @throws Exception 编号不是 UUID、笔记不存在，或 {@code record_type} 不是
     *         {@code exam_source} 时抛出 422
     */
    private VaultNote source(String key) throws Exception {
        require(key.matches("[0-9a-f-]{36}"), "体检记录编号无效");
        VaultNote note = vault.read(SOURCES + key + ".md");
        require("exam_source".equals(note.properties.get("record_type")), "不是体检报告来源"); return note;
    }
    /** 取当前可展示的解读版本：最新版有效则返回最新版，否则回退到旧版；都无效返回 0。 */
    private int existingVersion(String key, VaultNote note) throws Exception {
        return availableVersion(key,note,ENRICHED_VERSION);
    }

    private int availableVersion(String key, VaultNote note, int from) throws Exception {
        for (int version=from; version>=2; version--) {
            if (validReport(reportPath(key,note,version),note)) return version;
        }
        return Files.isRegularFile(vault.safe(reportPath(key,note,1))) ? 1 : 0;
    }

    /**
     * 判断某路径上的草稿是否属于这份来源的当前版本。
     *
     * @param path 草稿相对路径
     * @param note 体检来源笔记，用它的 revision 与草稿的 {@code source_revision} 比对
     * @return 文件存在、可解析、{@code record_type=exam_analysis} 且来源 revision 一致时
     *         为 {@code true}；读取失败一律视为不可信
     */
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

    /**
     * 计算草稿路径：{@code 80-AI分析/体检/<id>-<来源revision>[-vN].md}。
     *
     * @param version 1 表示旧版命名（无后缀），其余追加 {@code -vN} 以免互相覆盖
     */
    private static String reportPath(String key, VaultNote note, int version) {
        return REPORTS + key + "-" + note.revision + (version == 1 ? "" : "-v" + version) + ".md";
    }

    /**
     * 尝试把文本类原件解码成字符串，供摘录校验使用。
     *
     * @return 严格 UTF-8 解码的结果；非文本类型或编码无法解码时返回 {@code null}，
     *         此时跳过文字校验而不是猜测编码——错判编码会把正常资料判成不可信
     */
    private static String utf8Evidence(Attachment document) {
        if (!textLike(document.extension)) return null;
        try {
            return StandardCharsets.UTF_8.newDecoder().decode(ByteBuffer.wrap(document.bytes)).toString();
        } catch (CharacterCodingException unsupportedEncoding) {
            // 不猜测旧文本的字符编码，保留草稿让用户回查原件。
            return null;
        }
    }

    /**
     * 追加一段「原件摘录 + 位置 + 可选 AI 解读」的 Markdown 区块。
     *
     * @param heading 二级标题文本
     * @param entries 统一含 {@code quote} 与 {@code location}，观察项另含
     *                {@code interpretation}
     */
    private static void appendEvidence(StringBuilder markdown, String heading, List<Map<String,String>> entries) {
        if (entries.isEmpty()) return;
        markdown.append("## ").append(heading).append("\n\n");
        for (Map<String,String> entry : entries) {
            markdown.append(indent("原件摘录：" + entry.get("quote") + "\n位置：" + entry.get("location"))).append("\n\n");
            if (entry.containsKey("interpretation")) {
                markdown.append(indent("AI 解读：" + entry.get("interpretation"))).append("\n\n");
            }
            if (entry.containsKey("uncertainty") && !entry.get("uncertainty").isEmpty()) {
                markdown.append(indent("待核对：" + entry.get("uncertainty"))).append("\n\n");
            }
        }
    }
}
