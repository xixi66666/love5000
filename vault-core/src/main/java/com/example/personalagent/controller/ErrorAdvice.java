package com.example.personalagent.controller;
import com.example.personalagent.Api;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.http.*;
import java.util.*;
/**
 * 把后端异常统一翻译成 {@code {"success":false,"message":"..."}} 的 JSON 响应。
 *
 * <p>属 Controller 层的横切组件，对全部 {@code /api/} 下的请求生效。分派顺序由
 * Spring 按「最具体的异常类型优先」决定：上传超限、缺少 multipart 部件、业务状态
 * 异常、参数格式异常、其余异常各占一条通道，因此
 * {@link com.example.personalagent.Api#require} 抛出的 422 不会被最末的兜底分支
 * 吞成 500。</p>
 *
 * <p>面向用户的信息只给排查方向，不回显堆栈、本机路径或上游报文，避免私密目录
 * 与模型细节出现在页面和日志里。</p>
 */
@RestControllerAdvice
public class ErrorAdvice {
    /** 请求体超过 multipart 上限（20 MB）时返回 413 与可读提示；12 MB 的业务上限由附件校验单独把关。 */
    @ExceptionHandler(org.springframework.web.multipart.MaxUploadSizeExceededException.class) public ResponseEntity<?> oversized(Exception e){return ResponseEntity.status(413).body(Api.map("success",false,"message","文件太大，请选择不超过 12 MB 的文件"));}
    /** 缺少 multipart 文件或必填参数时返回 400；两类异常对用户同义，故合并为一条提示。 */
    @ExceptionHandler({org.springframework.web.multipart.support.MissingServletRequestPartException.class,org.springframework.web.bind.MissingServletRequestParameterException.class}) public ResponseEntity<?> missing(Exception e){return ResponseEntity.badRequest().body(Api.map("success",false,"message","缺少文件或必填字段，请核对后重试"));}
    /** 透传 {@link ResponseStatusException} 自带的状态码与原因，是业务校验的主要出口。 */
    @ExceptionHandler(ResponseStatusException.class) public ResponseEntity<?> expected(ResponseStatusException e){return ResponseEntity.status(e.getStatus()).body(Api.map("success",false,"message",e.getReason()));}
    /** 请求体无法反序列化或服务端判定参数非法时返回 400，不透露具体字段值。 */
    @ExceptionHandler({IllegalArgumentException.class,org.springframework.http.converter.HttpMessageNotReadableException.class}) public ResponseEntity<?> invalid(Exception e){return ResponseEntity.badRequest().body(Api.map("success",false,"message","输入格式无效，请检查字段"));}
    /**
     * 兜底分支：未预期异常一律返回 500 与固定的排查提示。
     *
     * <p>真实异常只进日志、不进响应体，避免把本机绝对路径、模型密钥或上游返回片段
     * 泄露到前端。</p>
     */
    @ExceptionHandler(Exception.class) public ResponseEntity<?> unexpected(Exception e){return ResponseEntity.status(500).body(Api.map("success",false,"message","操作未完成，请检查本地数据目录与服务状态"));}
}
