package com.example.website.prompt.library.dto;

public class PromptCreateResponse {

    private boolean success = true;
    private PromptDetailResponse.EntryDetail entry;

    public boolean isSuccess() {
        return success;
    }

    public void setSuccess(boolean success) {
        this.success = success;
    }

    public PromptDetailResponse.EntryDetail getEntry() {
        return entry;
    }

    public void setEntry(PromptDetailResponse.EntryDetail entry) {
        this.entry = entry;
    }
}