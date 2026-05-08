package com.example.imagetemplate.dto;

import java.util.LinkedHashMap;
import java.util.Map;

public class PromptRenderRequest {

    private Map<String, Object> variables = new LinkedHashMap<String, Object>();

    private String extraInstruction;

    public Map<String, Object> getVariables() {
        return variables;
    }

    public void setVariables(Map<String, Object> variables) {
        this.variables = variables;
    }

    public String getExtraInstruction() {
        return extraInstruction;
    }

    public void setExtraInstruction(String extraInstruction) {
        this.extraInstruction = extraInstruction;
    }
}
