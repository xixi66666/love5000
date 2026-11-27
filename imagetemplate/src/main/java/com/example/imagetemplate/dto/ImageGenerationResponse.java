package com.example.imagetemplate.dto;

import java.util.Map;

/**
 * 图片生成成功响应。
 *
 * <p>只有成功路径才会构造本对象（{@code success} 恒为 true）；失败由
 * {@link com.example.imagetemplate.service.ImageGenerationException} 冒泡到 Controller
 * 的异常处理器，输出 {@code {success:false, message}}。前端因此需要同时处理非 2xx 的错误体。</p>
 *
 * <p>{@code imageBase64} 是兆级字符串，前端还会再拼一个同等规模的 data URL；
 * 不要在日志或异常消息里输出整个字段。</p>
 */
public class ImageGenerationResponse {

    /** 是否成功；当前实现恒为 true，失败不会返回本类型。 */
    private boolean success;

    /** 发起生成的模板 ID，便于前端把结果关联回模板卡片。 */
    private String templateId;

    /** 实际使用的图片模型 ID（可能被请求覆盖，不一定是默认模型）。 */
    private String model;

    /** 本次实际发送给上游的最终 prompt，用于复现与排错；直接指定 prompt 时即原样。 */
    private String prompt;

    /** 图片 MIME 类型，由输出格式推导：image/png、image/jpeg 或 image/webp。 */
    private String mimeType;

    /** 归一化后的输出格式（小写），与请求一致，未传时为 png。 */
    private String outputFormat;

    /** 图片的 base64 编码，不含 {@code data:} 前缀；单张结果可达数 MB。 */
    private String imageBase64;

    /** 可直接作为前端图片元素 src 或下载链接的 data URL：{@code data:<mime>;base64,<...>}。 */
    private String dataUrl;

    /** 上游返回的 usage 原样透传，可能为 {@code null}；内容随提供方变化，不宜强类型依赖。 */
    private Map<String, Object> usage;

    public boolean isSuccess() {
        return success;
    }

    public void setSuccess(boolean success) {
        this.success = success;
    }

    public String getTemplateId() {
        return templateId;
    }

    public void setTemplateId(String templateId) {
        this.templateId = templateId;
    }

    public String getModel() {
        return model;
    }

    public void setModel(String model) {
        this.model = model;
    }

    public String getPrompt() {
        return prompt;
    }

    public void setPrompt(String prompt) {
        this.prompt = prompt;
    }

    public String getMimeType() {
        return mimeType;
    }

    public void setMimeType(String mimeType) {
        this.mimeType = mimeType;
    }

    public String getOutputFormat() {
        return outputFormat;
    }

    public void setOutputFormat(String outputFormat) {
        this.outputFormat = outputFormat;
    }

    public String getImageBase64() {
        return imageBase64;
    }

    public void setImageBase64(String imageBase64) {
        this.imageBase64 = imageBase64;
    }

    public String getDataUrl() {
        return dataUrl;
    }

    public void setDataUrl(String dataUrl) {
        this.dataUrl = dataUrl;
    }

    public Map<String, Object> getUsage() {
        return usage;
    }

    public void setUsage(Map<String, Object> usage) {
        this.usage = usage;
    }
}

