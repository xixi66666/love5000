package com.example.common.auth.exception;

import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

import java.util.Collections;
import java.util.List;

/**
 * 认证与授权失败的统一业务异常。
 *
 * <p>继承 {@code ResponseStatusException}，把 HTTP 状态码、稳定错误码 {@code code}
 * 与可展示的逐条说明 {@code details} 打包在一起：状态码决定响应状态，
 * {@code code} 供前端做分支判断，{@code details} 用于表单逐项提示。</p>
 *
 * <p>由 {@code AuthExceptionHandler} 统一转换为
 * {@code {success:false, code, message, details}}，因此 reason 只写对用户有意义的说明，
 * 不要把密码、摘要或数据库细节写进消息。</p>
 */
public class AuthException extends ResponseStatusException {

    /** 稳定错误码，供前端分支判断，不做本地化。 */
    private final String code;

    /** 逐条可展示的校验说明；构造时把 null 归一为空列表，调用方无需判空。 */
    private final List<String> details;

    /**
     * 使用默认错误码 {@code AUTH_ERROR} 且不带明细构造异常。
     *
     * @param status 返回给客户端的 HTTP 状态，通常为 400 / 401
     * @param reason 面向调用方的简短原因，会作为响应 message
     */
    public AuthException(HttpStatus status, String reason) {
        this(status, reason, "AUTH_ERROR", Collections.emptyList());
    }

    /**
     * 携带错误码与逐条明细构造异常。
     *
     * @param status 返回给客户端的 HTTP 状态
     * @param reason 面向调用方的简短原因
     * @param code 稳定错误码，例如 {@code USERNAME_EXISTS}、{@code PASSWORD_INVALID}
     * @param details 逐条说明，可为 {@code null}，此时按空列表处理
     */
    public AuthException(HttpStatus status, String reason, String code, List<String> details) {
        super(status, reason);
        this.code = code;
        this.details = details == null ? Collections.emptyList() : details;
    }

    public String getCode() {
        return code;
    }

    public List<String> getDetails() {
        return details;
    }
}
