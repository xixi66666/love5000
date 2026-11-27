package com.example.imagetemplate.dto;

/**
 * prompt 渲染结果。
 *
 * <p>Controller 只在渲染成功时用三参构造器创建本对象，因此 {@code success} 恒为 true；
 * 模板不存在等失败由异常处理器返回 {@code {success:false, message}}。
 * 无参构造器只为序列化与测试保留，用它创建的对象 {@code success} 默认是 false。</p>
 */
public class PromptRenderResponse {

    /** 恒为 true；渲染失败不会返回本类型。 */
    private boolean success;

    /** 被渲染的模板 ID，原样回显请求路径中的 id。 */
    private String templateId;

    /** 渲染后的完整提示词，可直接复制到图片生成接口使用。 */
    private String prompt;

    public PromptRenderResponse() {
    }

    public PromptRenderResponse(boolean success, String templateId, String prompt) {
        this.success = success;
        this.templateId = templateId;
        this.prompt = prompt;
    }

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

    public String getPrompt() {
        return prompt;
    }

    public void setPrompt(String prompt) {
        this.prompt = prompt;
    }
}

