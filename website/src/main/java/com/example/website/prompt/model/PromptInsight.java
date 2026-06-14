package com.example.website.prompt.model;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

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
