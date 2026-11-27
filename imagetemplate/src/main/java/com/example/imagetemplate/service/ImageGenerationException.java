package com.example.imagetemplate.service;

/**
 * 图片生成链路的统一运行时异常。
 *
 * <p>位于 service 层，由 {@link OpenAiImageGenerationService} 在四类场景抛出：
 * 请求参数（尺寸、模型名、参考图）不合法、未配置 {@code image.api-key}、
 * 上游 /images/generations 或 /images/edits 返回非 2xx、以及响应体缺少
 * {@code data[0].b64_json}。异常消息直接面向调用方展示，Controller 会把它
 * 映射成 {@code success=false} 与可读的 {@code message}，因此不要吞掉上游错误文本。</p>
 */
public class ImageGenerationException extends RuntimeException {

    /**
     * 用可读原因构造异常。
     *
     * @param message 面向调用方的失败原因；应为中文或包含上游响应片段的英文说明
     */
    public ImageGenerationException(String message) {
        super(message);
    }

    /**
     * 保留原始 cause，便于排查网络层或解析层问题。
     *
     * @param message 面向调用方的失败原因
     * @param cause   上游异常（如 {@code HttpStatusCodeException}、{@code NumberFormatException}）
     */
    public ImageGenerationException(String message, Throwable cause) {
        super(message, cause);
    }
}
