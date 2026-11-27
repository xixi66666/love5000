package com.example.website.prompt.library.dto;

/**
 * {@code POST /api/prompts} 的请求体，由 Jackson 从 JSON 反序列化。
 *
 * <p>六个字段都是字符串，且都允许缺省：{@code title}、{@code category}、{@code prompt} 为必填，
 * 由 {@code PromptLibraryServiceImpl#create} 做去空白与长度校验，上限依次是标题 512、
 * 小分类 128、正文 60000、标签 1000、来源链接 512、授权 255 个字符；超限统一抛
 * {@link IllegalArgumentException} 并由控制器转成 HTTP 400。</p>
 *
 * <p>{@code tags} 允许用中文或英文逗号分隔，服务端会去空白、去重并以英文逗号重新拼接后落库。</p>
 */
public class PromptCreateRequest {

    private String title;
    private String category;
    private String prompt;
    private String tags;
    private String sourceUrl;
    private String license;

    public String getTitle() {
        return title;
    }

    public void setTitle(String title) {
        this.title = title;
    }

    public String getCategory() {
        return category;
    }

    public void setCategory(String category) {
        this.category = category;
    }

    public String getPrompt() {
        return prompt;
    }

    public void setPrompt(String prompt) {
        this.prompt = prompt;
    }

    public String getTags() {
        return tags;
    }

    public void setTags(String tags) {
        this.tags = tags;
    }

    public String getSourceUrl() {
        return sourceUrl;
    }

    public void setSourceUrl(String sourceUrl) {
        this.sourceUrl = sourceUrl;
    }

    public String getLicense() {
        return license;
    }

    public void setLicense(String license) {
        this.license = license;
    }
}