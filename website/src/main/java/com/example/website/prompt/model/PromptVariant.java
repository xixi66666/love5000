package com.example.website.prompt.model;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * 拼装结果中的一个提示词版本：通用版、图片版、视频分镜版、海报版或短提示词版。
 *
 * <p>{@code type} 是稳定的机器标识（同时用于排序和去重），{@code title} 是中文展示名；
 * {@code sections} 列出该版本覆盖的结构要素（如主体、镜头、负面限制），供前端渲染成标签；
 * {@code sourceIds} 记录参与拼装的来源。两个列表在构造和 setter 里都做空值兜底并复制，
 * getter 返回不可修改视图。</p>
 */
public class PromptVariant {

    private String type;
    private String title;
    private String prompt;
    private List<String> sourceIds = new ArrayList<String>();
    private List<String> sections = new ArrayList<String>();

    public PromptVariant() {
    }

    /**
     * 全量构造一个版本。
     *
     * @param type      版本类型标识，例如 {@code image}
     * @param title     中文展示名
     * @param prompt    已拼好的提示词正文，可能带“参考来源综合”前缀
     * @param sourceIds 参与拼装的来源 id，允许 {@code null}（转为空列表）
     * @param sections  该版本覆盖的结构要素，允许 {@code null}（转为空列表）
     */
    public PromptVariant(String type, String title, String prompt, List<String> sourceIds, List<String> sections) {
        this.type = type;
        this.title = title;
        this.prompt = prompt;
        this.sourceIds = sourceIds == null ? new ArrayList<String>() : new ArrayList<String>(sourceIds);
        this.sections = sections == null ? new ArrayList<String>() : new ArrayList<String>(sections);
    }

    public String getType() {
        return type;
    }

    public void setType(String type) {
        this.type = type;
    }

    public String getTitle() {
        return title;
    }

    public void setTitle(String title) {
        this.title = title;
    }

    public String getPrompt() {
        return prompt;
    }

    public void setPrompt(String prompt) {
        this.prompt = prompt;
    }

    public List<String> getSourceIds() {
        return Collections.unmodifiableList(sourceIds);
    }

    public void setSourceIds(List<String> sourceIds) {
        this.sourceIds = sourceIds == null ? new ArrayList<String>() : new ArrayList<String>(sourceIds);
    }

    public List<String> getSections() {
        return Collections.unmodifiableList(sections);
    }

    public void setSections(List<String> sections) {
        this.sections = sections == null ? new ArrayList<String>() : new ArrayList<String>(sections);
    }
}
