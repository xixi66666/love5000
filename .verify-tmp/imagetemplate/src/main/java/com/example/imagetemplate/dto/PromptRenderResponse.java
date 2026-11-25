package com.example.imagetemplate.dto;

public class PromptRenderResponse {

    private boolean success;

    private String templateId;

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
