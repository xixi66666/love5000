package com.example.imagetemplate.model;

public class LibraryAggregationStatus {

    private String status;

    private int expectedCuratedCount;

    private int loadedCuratedCount;

    private int expectedLibraryCount;

    private int loadedLibraryCount;

    private int total;

    private String message;

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public int getExpectedCuratedCount() {
        return expectedCuratedCount;
    }

    public void setExpectedCuratedCount(int expectedCuratedCount) {
        this.expectedCuratedCount = expectedCuratedCount;
    }

    public int getLoadedCuratedCount() {
        return loadedCuratedCount;
    }

    public void setLoadedCuratedCount(int loadedCuratedCount) {
        this.loadedCuratedCount = loadedCuratedCount;
    }

    public int getExpectedLibraryCount() {
        return expectedLibraryCount;
    }

    public void setExpectedLibraryCount(int expectedLibraryCount) {
        this.expectedLibraryCount = expectedLibraryCount;
    }

    public int getLoadedLibraryCount() {
        return loadedLibraryCount;
    }

    public void setLoadedLibraryCount(int loadedLibraryCount) {
        this.loadedLibraryCount = loadedLibraryCount;
    }

    public int getTotal() {
        return total;
    }

    public void setTotal(int total) {
        this.total = total;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }
}
