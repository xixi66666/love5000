package com.example.personalagent.service;

import com.fasterxml.jackson.databind.JsonNode;
import org.apache.pdfbox.io.MemoryUsageSetting;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.rendering.ImageType;
import org.apache.pdfbox.rendering.PDFRenderer;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import javax.imageio.ImageIO;
import java.io.*;
import java.util.*;

import static com.example.personalagent.Api.require;

/** 收录本机表格和显式授权的视觉转录，保留两者各自的证据可信度。 */
@Service
public class ExamDocumentAnalysis {
    static final String LOCAL = "mirobody_local", OCR = "mirobody_ocr";
    private static final int OCR_MAX_PAGES = 10;
    private static final Set<String> LOCAL_TYPES = new HashSet<>(Arrays.asList("pdf","xlsx","docx"));
    private static final Map<String,String> IMAGE_TYPES = new HashMap<>();
    static {
        IMAGE_TYPES.put("png","image/png"); IMAGE_TYPES.put("jpg","image/jpeg");
        IMAGE_TYPES.put("jpeg","image/jpeg"); IMAGE_TYPES.put("webp","image/webp");
    }
    private final MirobodyEngine engine;
    private final AiGateway gateway;

    public ExamDocumentAnalysis(MirobodyEngine engine, AiGateway gateway) { this.engine = engine; this.gateway = gateway; }

    boolean canParseLocal(String extension) { return LOCAL_TYPES.contains(extension) && engine.available(); }

    boolean canUseOcr(String extension, ExamPdfText pdf) {
        return (("pdf".equals(extension) && pdf.pageCount > 0 && pdf.pageCount <= OCR_MAX_PAGES)
            || IMAGE_TYPES.containsKey(extension)) && engine.available();
    }

    ExamFindings parse(LocalDocuments.Attachment document, ExamPdfText pdf, boolean ocr) throws IOException {
        require(ocr ? canUseOcr(document.extension,pdf) : canParseLocal(document.extension),
            "当前文档无法使用此解析方式，请检查格式与 Mirobody 依赖。PDF 分页识别最多 10 页。");
        JsonNode response = ocr ? engine.parseTranscripts(transcribe(document)) : engine.parse(document.bytes,document.extension);
        ExamFindings findings = new ExamFindings();
        findings.documentMethod = ocr ? OCR : LOCAL;
        findings.omittedEvidence = Math.max(0,response.path("omitted").asInt());
        for (JsonNode row : ExamFindings.array(response,"metrics",400)) {
            if (!row.isObject()) throw new IOException("Mirobody row");
            Map<String,String> evidence = new LinkedHashMap<>();
            evidence.put("quote",ExamFindings.field(row.get("quote"),500,true));
            String location = ExamFindings.field(row.get("location"),100,true);
            if ("pdf".equals(document.extension) && !validPage(location,pdf.pageCount)) throw new IOException("Mirobody page");
            evidence.put("location",location);
            findings.metrics.add(ExamFindings.metric(row,evidence));
        }
        if (findings.metrics.isEmpty()) throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY,
            "未找到可回查的表格指标。可尝试分页视觉识别、AI 解读或核对原件。原件仍已归档。");
        findings.textEvidenceVerified = !ocr;
        findings.pdfPageEvidenceVerified = !ocr && "pdf".equals(document.extension);
        findings.summary = String.format("%s提取了 %d 项指标。",ocr ? "分页视觉识别" : "本机表格解析",findings.metrics.size());
        if (ocr) findings.limitations.add("视觉转录需对照原件复核，暂不参与历年指标关联。");
        else if ("pdf".equals(document.extension) && pdf.readableCount < pdf.pageCount) {
            findings.limitations.add("报告存在缺少文字层的页面，本机解析仅覆盖可读取的表格。");
        }
        return findings;
    }

    private List<String> transcribe(LocalDocuments.Attachment document) throws IOException {
        if (!"pdf".equals(document.extension)) {
            require(document.bytes.length <= 6 * 1024 * 1024,"图片超过 6 MB，请压缩后重新导入。");
            return Collections.singletonList(readImage(IMAGE_TYPES.get(document.extension),document.bytes));
        }
        List<String> pages = new ArrayList<>();
        try (PDDocument original = PDDocument.load(new ByteArrayInputStream(document.bytes),MemoryUsageSetting.setupMainMemoryOnly(64L*1024*1024))) {
            PDFRenderer renderer = new PDFRenderer(original);
            renderer.setSubsamplingAllowed(true);
            for (int i = 0; i < original.getNumberOfPages(); i++) {
                PDRectangle box = original.getPage(i).getCropBox();
                float longest = Math.max(box.getWidth(),box.getHeight());
                if (!Float.isFinite(longest) || longest <= 0) throw new IOException("PDF page size");
                ByteArrayOutputStream image = new ByteArrayOutputStream();
                ImageIO.write(renderer.renderImage(i,Math.min(2.5f,1800 / longest),ImageType.RGB),"png",image);
                pages.add(readImage("image/png",image.toByteArray()));
            }
        }
        return pages;
    }

    private String readImage(String mime, byte[] image) {
        try { return gateway.readExamImage(mime,image); }
        catch (AiGateway.MissingModelException missing) {
            throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY,"请在根 model.properties 配置 vision provider 后重试。原件仍已归档。");
        } catch (Exception unavailable) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY,"视觉模型未能完成分页识别。原件仍已归档，可重试。");
        }
    }

    private static boolean validPage(String location, int pageCount) {
        java.util.regex.Matcher match = java.util.regex.Pattern.compile("第 ([1-9][0-9]?) 页").matcher(location);
        return match.matches() && Integer.parseInt(match.group(1)) <= pageCount;
    }
}
