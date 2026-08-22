package com.example.imagetemplate.dto;

import java.util.ArrayList;
import java.util.List;

public class ImageTemplatePageResponse {

    private boolean success = true;

    private int total;

    private int page;

    private int size;

    private boolean hasMore;

    private String libraryStatus;

    private String message;

    private List<ImageTemplateSummaryResponse> templates =
            new ArrayList<ImageTemplateSummaryResponse>();

    public boolean isSuccess() {
        return success;
    }

    public int getTotal() {
        return total;
    }

    public void setTotal(int total) {
        this.total = total;
    }

    public int getPage() {
        return page;
    }

    public void setPage(int page) {
        this.page = page;
    }

    public int getSize() {
        return size;
    }

    public void setSize(int size) {
        this.size = size;
    }

    public boolean isHasMore() {
        return hasMore;
    }

    public void setHasMore(boolean hasMore) {
        this.hasMore = hasMore;
    }

    public String getLibraryStatus() {
        return libraryStatus;
    }

    public void setLibraryStatus(String libraryStatus) {
        this.libraryStatus = libraryStatus;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }

    public List<ImageTemplateSummaryResponse> getTemplates() {
        return templates;
    }

    public void setTemplates(List<ImageTemplateSummaryResponse> templates) {
        this.templates = templates;
    }
}
