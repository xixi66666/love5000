package com.example.personalagent.controller;

import com.example.personalagent.service.HealthArchive;
import org.springframework.core.io.FileSystemResource;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import java.nio.file.Path;
import java.util.Map;
import static com.example.personalagent.Api.ok;

/**
 * 健康档案（体检）接口，挂在 {@code /api/exams} 下。
 *
 * <p>属 Controller 层：只做参数绑定与响应包装；目录约定、原件哈希校验、文字层预览、
 * AI 解读与版本管理全部在 {@link HealthArchive} 内完成。接口分三类：列表与详情、
 * 原件下载与预览、解读草稿生成。</p>
 *
 * <p>所有接口都要求登录态，写接口额外要求 {@code X-CSRF-Token}，由
 * {@link com.example.personalagent.security.LocalSecurity} 统一校验；这里不做
 * 权限判断，以免与拦截器规则出现两套口径。</p>
 */
@RestController
@RequestMapping("/api/exams")
public class ExamController {
    private final HealthArchive archive;
    public ExamController(HealthArchive archive) { this.archive = archive; }

    /** 列出全部体检来源，按检查日期倒序，并标注是否已有可读的解读草稿。 */
    @GetMapping public Object list() throws Exception { return ok(archive.overview()); }
    @GetMapping("/timeline") public Object timeline() throws Exception { return ok(archive.timeline()); }
    /** 单份体检的详情：来源信息、已核对文字、当前与上一版草稿路径、解析出的发现。 */
    @GetMapping("/{id}") public Object detail(@PathVariable String id) throws Exception { return ok(archive.detail(id)); }
    /** 在本机解析原件文字层生成预览，不向任何外部模型发送内容。 */
    @GetMapping("/{id}/preview") public Object preview(@PathVariable String id) throws Exception { return ok(archive.preview(id)); }
    /**
     * 归档一份体检原件，可选地立即发起一次 AI 解读。
     *
     * @param file   原件，大小与后缀受 {@link LocalDocuments.Attachment} 限制
     * @param fields 表单字段：必填 {@code date}（{@code yyyy-MM-dd}）与 {@code workspace}；
     *               {@code mode=analyze} 表示归档后立即解读，需同时传 {@code consent=true}；
     *               可选 {@code import_id}（UUID v4）用于批量导入失败后重试
     * @return {@code id}、{@code revision}、{@code path}；解读失败时另附 {@code warning}，
     *         已保存的原件不回滚
     * @throws Exception 日期非法、编号格式不符，或重试编号与既有记录内容不一致时抛出
     */
    @PostMapping(consumes=MediaType.MULTIPART_FORM_DATA_VALUE)
    public Object save(@RequestParam MultipartFile file, @RequestParam Map<String,String> fields) throws Exception {
        return ok(archive.archive(file, fields));
    }
    /**
     * 为指定体检记录生成 AI 解读草稿。
     *
     * @param id      体检记录编号（UUID）
     * @param request 请求体：{@code consent}、来源 {@code revision}、{@code workspace}，
     *                可选 {@code evidence_mode}（{@code pdf_text} 用本机提取文字，
     *                {@code original} 允许上传完整原件，{@code mirobody_local} 本机表格，
     *                {@code mirobody_ocr} 授权后执行分页视觉识别）
     * @return 写入草稿后的详情，含 {@code analysis_version} 与 {@code report_path}
     * @throws Exception 未确认授权、来源已变化或模型输出无法与原件对上时抛出
     */
    @PostMapping("/{id}/analysis") public Object analyze(@PathVariable String id, @RequestBody Map<String,Object> request) throws Exception {
        return ok(archive.analyze(id,request));
    }
    /**
     * 下载体检原件，文件名加 {@code exam-} 前缀以免与导入资料混淆。
     *
     * @param id 体检记录编号
     * @return 八位字节流下载响应
     * @throws Exception 原件被移动，或哈希与归档时不一致时抛出
     */
    @GetMapping("/{id}/original") public ResponseEntity<FileSystemResource> original(@PathVariable String id) throws Exception {
        Path original = archive.original(id);
        return ResponseEntity.ok().contentType(MediaType.APPLICATION_OCTET_STREAM)
            .header(HttpHeaders.CONTENT_DISPOSITION,"attachment; filename=\"exam-" + original.getFileName() + "\"")
            .body(new FileSystemResource(original));
    }
}
