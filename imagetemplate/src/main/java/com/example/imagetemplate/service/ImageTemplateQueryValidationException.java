package com.example.imagetemplate.service;

/**
 * 列表查询参数不合法时抛出。
 *
 * <p>当前只在 {@link ImagePromptTemplateService#search} 的入参校验中触发：
 * {@code page < 1} 或 {@code size} 不在 1 到 100 之间（上限与前端“加载更多”约定一致）。
 * Controller 将其映射为 HTTP 400 与 {@code success=false}，消息为中文，
 * 便于直接展示给页面用户。</p>
 */
public class ImageTemplateQueryValidationException extends RuntimeException {

    /**
     * 用可读的中文校验提示构造异常。
     *
     * @param message 面向页面的校验失败原因
     */
    public ImageTemplateQueryValidationException(String message) {
        super(message);
    }
}
