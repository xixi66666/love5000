package com.example.imagetemplate.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

import java.util.ArrayList;
import java.util.List;

@JsonIgnoreProperties(ignoreUnknown = true)
public class PromptLibraryCatalog {

    private String generatedAt;

    private boolean authorizedByUser;

    private List<PromptLibrarySource> sources = new ArrayList<PromptLibrarySource>();

    private List<PromptLibraryEntry> entries = new ArrayList<PromptLibraryEntry>();

    public String getGeneratedAt() {
        return generatedAt;
    }

    public void setGeneratedAt(String generatedAt) {
        this.generatedAt = generatedAt;
    }

    public boolean isAuthorizedByUser() {
        return authorizedByUser;
    }

    public void setAuthorizedByUser(boolean authorizedByUser) {
        this.authorizedByUser = authorizedByUser;
    }

    public List<PromptLibrarySource> getSources() {
        return sources;
    }

    public void setSources(List<PromptLibrarySource> sources) {
        this.sources = sources;
    }

    public List<PromptLibraryEntry> getEntries() {
        return entries;
    }

    public void setEntries(List<PromptLibraryEntry> entries) {
        this.entries = entries;
    }
}
