package com.example.website.prompt.dto;

import java.util.ArrayList;
import java.util.List;

public class PromptSourceRefreshRequest {

    private List<String> sourceIds = new ArrayList<String>();

    public List<String> getSourceIds() {
        return sourceIds;
    }

    public void setSourceIds(List<String> sourceIds) {
        this.sourceIds = sourceIds == null ? new ArrayList<String>() : new ArrayList<String>(sourceIds);
    }
}
