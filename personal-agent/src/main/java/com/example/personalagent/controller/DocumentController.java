package com.example.personalagent.controller;

import com.example.personalagent.service.LocalDocuments;
import org.springframework.core.io.FileSystemResource;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.nio.file.Path;
import java.util.Map;

import static com.example.personalagent.Api.*;

/**
 * 通用资料导入接口，挂在 {@code /api/documents} 下。
 *
 * <p>属 Controller 层：只做参数绑定与响应包装，文件写入、哈希校验与可选的 AI 整理
 * 全部委托给 {@link LocalDocuments}。所有写接口要求 {@code multipart/form-data}，
 * 并由 {@link com.example.personalagent.security.LocalSecurity} 统一校验 Session
 * 与 CSRF 头。</p>
 *
 * <p>导入接口只回传笔记相对路径；原件只经下载接口返回，
 * 这样每次读取都能重新校验哈希。</p>
 */
@RestController
@RequestMapping("/api/documents")
public class DocumentController {
    private final LocalDocuments documents;

    public DocumentController(LocalDocuments documents) {
        this.documents = documents;
    }

    /**
     * 导入一份资料：原件落到 {@code 99-附件/导入资料/}，并在对应领域目录生成笔记。
     *
     * @param file   原件，最大 12 MB，后缀受 {@link LocalDocuments} 白名单限制
     * @param fields 表单字段：{@code domain}、{@code title}、可选 {@code date}、
     *               {@code mode}（{@code archive} 仅归档或 {@code analyze} 归档并整理）、
     *               {@code workspace}，以及选择整理时必需的 {@code consent=true}
     * @return {@code success/data.path}，只回传笔记相对路径
     * @throws Exception 字段校验、原件校验或写盘失败时抛出，由 ErrorAdvice 转成
     *         带中文提示的 4xx/5xx 响应
     */
    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public Object save(@RequestParam MultipartFile file, @RequestParam Map<String,String> fields) throws Exception {
        return ok(map("path", documents.archive(file, fields).path));
    }

    /**
     * 下载导入记录对应的原件。
     *
     * <p>每次都重新校验大小与哈希，原件被外部改动后拒绝下载而不是返回可疑内容；
     * 响应固定为 {@code attachment}，不会被浏览器内联渲染。</p>
     *
     * @param path 导入笔记的相对路径，必须指向 {@code record_type=imported_document}
     *             且文件名为 UUID 的记录
     * @return 以八位字节流返回的原件，文件名取原件在 Vault 中的真实名字
     * @throws Exception 记录不存在、缺少原件或哈希与归档时不一致时抛出
     */
    @GetMapping("/original")
    public ResponseEntity<FileSystemResource> original(@RequestParam String path) throws Exception {
        Path original = documents.original(path);
        return ResponseEntity.ok().contentType(MediaType.APPLICATION_OCTET_STREAM)
            .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + original.getFileName() + "\"")
            .body(new FileSystemResource(original));
    }
}
