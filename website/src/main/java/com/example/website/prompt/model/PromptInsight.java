package com.example.website.prompt.model;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * 单个来源的要点集合模型。
 *
 * <p>当前代码中没有接口或服务引用它，是早期提示词控制台版本遗留的数据形状；保留在模型包里，
 * 便于恢复“来源要点”展示时直接复用。它不是 {@code /api/prompts} 系列接口的返回结构。</p>
 */
public class PromptInsight {

    private String sourceId;
    private List<String> points = new ArrayList<String>();

    public PromptInsight() {
    }

    public PromptInsight(String sourceId, List<String> points) {
        this.sourceId = sourceId;
        this.points = points == null ? new ArrayList<String>() : new ArrayList<String>(points);
    }

    public String getSourceId() {
        return sourceId;
    }

    public void setSourceId(String sourceId) {
        this.sourceId = sourceId;
    }

    public List<String> getPoints() {
        return Collections.unmodifiableList(points);
    }

    public void setPoints(List<String> points) {
        this.points = points == null ? new ArrayList<String>() : new ArrayList<String>(points);
    }
}
