package com.example.website.prompt.model;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public class PromptVariant {

    private String type;
    private String title;
    private String prompt;
    private List<String> sourceIds = new ArrayList<String>();
    private List<String> sections = new ArrayList<String>();

    public PromptVariant() {
    }

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
