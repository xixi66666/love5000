package com.example.website.prompt.dto;

import java.util.ArrayList;
import java.util.List;

/**
 * {@code POST /api/prompts/compose} 的请求体。
 *
 * <p>只有 {@code scene} 必填。{@code purpose} 决定输出的第一个模板类型（{@code image}、
 * {@code video}、{@code poster}，其余取值落到通用版）；{@code tone} 缺省为
 * “专业、清晰、有画面感”，{@code length} 缺省为 {@code balanced}；{@code sourceIds} 为空表示使用
 * 全部白名单来源，全部无效时同样回退为全部来源。这些归一化规则都在
 * {@code PromptComposeService#compose} 里执行，本类只承载入参。</p>
 */
public class PromptComposeRequest {

    private String scene;
    private String purpose;
    private String tone;
    private String length;
    private List<String> sourceIds = new ArrayList<String>();

    public String getScene() {
        return scene;
    }

    public void setScene(String scene) {
        this.scene = scene;
    }

    public String getPurpose() {
        return purpose;
    }

    public void setPurpose(String purpose) {
        this.purpose = purpose;
    }

    public String getTone() {
        return tone;
    }

    public void setTone(String tone) {
        this.tone = tone;
    }

    public String getLength() {
        return length;
    }

    public void setLength(String length) {
        this.length = length;
    }

    public List<String> getSourceIds() {
        return sourceIds;
    }

    public void setSourceIds(List<String> sourceIds) {
        this.sourceIds = sourceIds == null ? new ArrayList<String>() : new ArrayList<String>(sourceIds);
    }
}
