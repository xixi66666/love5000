package com.example.personalagent.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.text.Normalizer;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import static com.example.personalagent.Api.map;

/** 原件字段与已查证的公开指南分开呈现，公开参考不参与报告异常标记。 */
final class ExamMetricReferences {
    private static final String CHECKED_ON = "2026-11-27";
    private static final Pattern EGFR_COMBINED = Pattern.compile("([<>≤≥]=?\\d+(?:\\.\\d+)?)\\s*(m[Ll]/min/1\\.73m(?:\\^2|²|2))");
    private static final Pattern MISSING = Pattern.compile("[-—–]+|未注明|未提供|未收录|不适用|无|N/?A",Pattern.CASE_INSENSITIVE);

    private ExamMetricReferences() {}

    static JsonNode annotate(ObjectMapper json, Object extracted) {
        JsonNode findings = json.valueToTree(extracted);
        boolean verified = findings.path("textEvidenceVerified").asBoolean(false);
        for (JsonNode value : findings.path("metrics")) {
            if (!value.isObject()) continue;
            ObjectNode row = (ObjectNode) value;
            row.remove("external_reference");
            row.remove("range_recovered");
            String range = row.path("range").asText("").trim();
            if (!range.isEmpty() && !MISSING.matcher(range).matches()) continue;
            row.put("range","");
            String name = compact(row.path("name").asText("")).toUpperCase(Locale.ROOT);
            String unit = row.path("unit").asText("").trim();
            if (verified && isEgfr(name) && recoverEgfr(row,unit)) continue;
            String normalizedUnit = compact(unit);
            if (name.matches("BMI|体质指数(?:\\(BMI\\))?|体重指数(?:\\(BMI\\))?")
                    && normalizedUnit.matches("kg/m(?:\\^2|2)")) {
                row.set("external_reference",reference(json,"指南分类",
                    "18.5 ≤ BMI < 24.0 kg/m²",
                    "一般成人 BMI 正常范围为 18.5 ≤ BMI < 24.0 kg/m²。",
                    "适用于中国一般成人。儿童青少年、孕期和高龄人群有专门标准。",
                    "国家卫生健康委《体重管理指导原则（2024 年版）》",
                    "https://www.nhc.gov.cn/wjw/ylyjs/202412/b3d40e0141834897808ce6c9dce76a60/files/1736390749000_59785.pdf"));
            } else if ("血压".equals(name) && "mmHg".equals(normalizedUnit)) {
                row.set("external_reference",reference(json,"成人诊室血压分级",
                    "收缩压 <120 且舒张压 <80 mmHg",
                    "正常为收缩压 <120 且舒张压 <80 mmHg。正常高值为收缩压 120–139 和/或舒张压 80–89 mmHg。",
                    "限成人规范诊室测量，收缩压与舒张压分属不同类别时以较高级别为准。一次测量只供筛查参考。",
                    "《中国高血压防治指南（2024 年修订版）》表 6",
                    "https://pmc.ncbi.nlm.nih.gov/articles/PMC11937835/"));
            } else if (isEgfr(name) && normalizedUnit.matches("m[Ll]/min/1\\.73m(?:\\^2|2)")) {
                row.set("external_reference",reference(json,"eGFR 指南分级",
                    "G1 ≥90，G2 60–89 mL/min/1.73 m²",
                    "G1 为 ≥90 mL/min/1.73 m²，G2 为 60–89 mL/min/1.73 m²。",
                    "这是肾小球滤过率分级。判断慢性肾病需结合肾损伤证据及持续时间。",
                    "KDIGO 2024 慢性肾病指南表 1、表 2",
                    "https://kdigo.org/wp-content/uploads/2024/03/KDIGO-2024-CKD-Guideline.pdf"));
            }
        }
        return findings;
    }

    private static boolean isEgfr(String name) {
        return "EGFR".equals(name) || "EGFR(CKD-EPI)".equals(name);
    }

    private static boolean recoverEgfr(ObjectNode row, String combined) {
        Matcher match = EGFR_COMBINED.matcher(combined);
        String value = row.path("value").asText(""), name = row.path("name").asText("");
        String quote = row.path("quote").asText("");
        // 旧草稿可能把 eGFR 行的参考阈值连同单位放进 unit 字段。只恢复原件中可确认的同一行。
        if (!match.matches() || !value.matches("\\d+(?:\\.\\d+)?") || !Pattern.compile(
                Pattern.quote(name) + "\\h+" + Pattern.quote(value) + "\\h+" + Pattern.quote(combined)).matcher(quote).find()) return false;
        row.put("range",match.group(1));
        row.put("unit",match.group(2));
        row.put("range_recovered",true);
        return true;
    }

    private static String compact(String value) {
        return Normalizer.normalize(value,Normalizer.Form.NFKC).replaceAll("[\\p{Z}\\s]+","");
    }

    private static JsonNode reference(ObjectMapper json, String label, String displayRange, String statement, String applies,
                                      String title, String url) {
        return json.valueToTree(map("label",label,"display_range",displayRange,"statement",statement,"applies_to",applies,
            "source_title",title,"source_url",url,"checked_on",CHECKED_ON));
    }
}
