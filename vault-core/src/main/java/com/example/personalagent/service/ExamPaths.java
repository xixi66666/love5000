package com.example.personalagent.service;

import java.nio.file.Paths;

/** Vault 中由健康应用管理的稳定目录。 */
public final class ExamPaths {
    public static final String SOURCES = "30-健康/体检/";
    public static final String ORIGINALS = "99-附件/体检/";
    public static final String REPORTS = "80-AI分析/体检/";

    private ExamPaths() {}

    static boolean manages(String path) {
        String normalized = Paths.get(path).normalize().toString().replace('\\','/');
        return normalized.startsWith(SOURCES) || normalized.startsWith(ORIGINALS) || normalized.startsWith(REPORTS);
    }
}
