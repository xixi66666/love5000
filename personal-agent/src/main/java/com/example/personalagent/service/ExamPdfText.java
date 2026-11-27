package com.example.personalagent.service;

import org.apache.pdfbox.io.MemoryUsageSetting;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.encryption.InvalidPasswordException;
import org.apache.pdfbox.text.PDFTextStripper;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.Writer;
import java.util.ArrayList;
import java.util.List;

import static com.example.personalagent.Api.map;

/** 在本机按实际页序读取 PDF 文字层，不渲染、打开或导出内嵌内容。 */
final class ExamPdfText {
    private static final int PAGE_LIMIT = 50;
    private static final int TEXT_LIMIT = 40000;
    final List<String> pages = new ArrayList<>();
    int pageCount;
    int readableCount;
    String mode = "original";
    String message = "分析时将按当前模型支持的方式发送此原件。";

    static ExamPdfText inspect(LocalDocuments.Attachment document) {
        ExamPdfText result = new ExamPdfText();
        if (!"pdf".equals(document.extension)) return result;
        try (PDDocument pdf = PDDocument.load(new ByteArrayInputStream(document.bytes),
                MemoryUsageSetting.setupMainMemoryOnly(64L * 1024 * 1024))) {
            if (pdf.isEncrypted() && !pdf.getCurrentAccessPermission().canExtractContent()) {
                return result.unavailable("此 PDF 禁止提取文字。请在有权限的情况下导出可读副本。");
            }
            result.pageCount = pdf.getNumberOfPages();
            if (result.pageCount == 0) return result.unavailable("PDF 没有页面，请重新导出报告。");
            if (result.pageCount > PAGE_LIMIT) {
                return result.unavailable("PDF 超过 50 页。请按检查报告拆分后重新导入。");
            }
            PDFTextStripper stripper = new PDFTextStripper();
            stripper.setSortByPosition(true);
            stripper.setShouldSeparateByBeads(false);
            int remaining = TEXT_LIMIT;
            for (int page = 1; page <= result.pageCount; page++) {
                stripper.setStartPage(page);
                stripper.setEndPage(page);
                PageWriter writer = new PageWriter(remaining);
                stripper.writeText(pdf, writer);
                String text = writer.text.toString().trim();
                result.pages.add(text);
                if (hasReadableText(text)) result.readableCount++;
                remaining -= text.length();
            }
            if (result.readableCount == result.pageCount) {
                result.mode = "pdf_text";
                result.message = "逐页文字已在本机提取。请核对表格列是否对齐，图片中的文字可能需要查看原件。";
            } else {
                result.message = "部分页面文字不可读，可能是扫描件或缺少文字层。请切换至 DeepSeek 识别原件，并对照原件核实结果。";
            }
        } catch (InvalidPasswordException locked) {
            return result.unavailable("PDF 需要密码。请在有权限的情况下导出可读副本。");
        } catch (TextLimitException tooLong) {
            return result.unavailable("PDF 文字超过 40,000 字符，请按检查报告拆分后重新导入。");
        } catch (IOException malformed) {
            return result.unavailable("无法读取 PDF，请确认文件可打开并重新导出后导入。");
        }
        return result;
    }

    private static boolean hasReadableText(String text) {
        return text.codePoints().filter(Character::isLetterOrDigit).limit(8).count() == 8;
    }

    private ExamPdfText unavailable(String reason) {
        mode = "unavailable";
        message = reason;
        pages.clear();
        readableCount = 0;
        return this;
    }

    Object preview() {
        List<Object> entries = new ArrayList<>();
        for (int index = 0; index < pages.size(); index++) {
            entries.add(map("page", index + 1, "text", pages.get(index)));
        }
        return map("mode", mode, "message", message, "page_count", pageCount,
            "readable_pages", readableCount, "pages", entries);
    }

    String modelInput() {
        List<String> sections = new ArrayList<>();
        for (int index = 0; index < pages.size(); index++) sections.add("[第 " + (index + 1) + " 页]\n" + pages.get(index));
        return String.join("\n\n", sections);
    }

    private static final class TextLimitException extends IOException {}

    private static final class PageWriter extends Writer {
        private final StringBuilder text = new StringBuilder();
        private final int limit;

        private PageWriter(int limit) { this.limit = limit; }

        @Override public void write(char[] value, int offset, int length) throws IOException {
            if (length > limit - text.length()) throw new TextLimitException();
            text.append(value, offset, length);
        }
        @Override public void flush() {}
        @Override public void close() {}
    }
}
