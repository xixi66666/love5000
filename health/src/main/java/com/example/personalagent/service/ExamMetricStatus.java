package com.example.personalagent.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.math.BigDecimal;
import java.text.Normalizer;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** 按本次报告的字段分类，外部参考仅供查阅。 */
final class ExamMetricStatus {
    static final String ABNORMAL = "abnormal";
    static final String NORMAL = "normal";
    static final String UNKNOWN = "unknown";
    private static final String NUMBER = "[+-]?\\d{1,12}(?:\\.\\d{1,8})?";
    private static final Pattern DECIMAL = Pattern.compile(NUMBER);
    private static final Pattern INTERVAL = Pattern.compile("(" + NUMBER + ")\\h*[-–—~～至]\\h*(" + NUMBER + ")");
    private static final Pattern LIMIT = Pattern.compile("(<=|>=|[<>≤≥])\\h*(" + NUMBER + ")");

    private ExamMetricStatus() {}

    static JsonNode annotate(JsonNode findings) {
        for (JsonNode row : findings.path("metrics")) {
            if (row.isObject()) ((ObjectNode) row).put("status", classify(row));
        }
        return findings;
    }

    private static String classify(JsonNode row) {
        String quote = row.path("quote").asText("");
        String flagStatus = reportedStatus(row.path("flag").asText(""), quote);
        if (!UNKNOWN.equals(flagStatus)) return flagStatus;

        String value = row.path("value").asText("").trim();
        String range = row.path("range").asText("").trim();
        if (value.isEmpty() || range.isEmpty() || !quote.contains(value) || !quote.contains(range)) return UNKNOWN;
        String normalizedValue = normalize(value), normalizedRange = normalize(range);
        if (normalizedValue.matches("阴性|阳性") && normalizedRange.matches("阴性|阳性")) {
            return normalizedValue.equals(normalizedRange) ? NORMAL : ABNORMAL;
        }
        if (!DECIMAL.matcher(normalizedValue).matches()) return UNKNOWN;
        BigDecimal measured = new BigDecimal(normalizedValue);
        Matcher interval = INTERVAL.matcher(normalizedRange);
        if (interval.matches()) {
            BigDecimal low = new BigDecimal(interval.group(1)), high = new BigDecimal(interval.group(2));
            if (low.compareTo(high) > 0) return UNKNOWN;
            return measured.compareTo(low) >= 0 && measured.compareTo(high) <= 0 ? NORMAL : ABNORMAL;
        }
        Matcher limit = LIMIT.matcher(normalizedRange);
        if (!limit.matches()) return UNKNOWN;
        String operator = limit.group(1);
        int comparison = measured.compareTo(new BigDecimal(limit.group(2)));
        boolean upperLimit = operator.startsWith("<") || "≤".equals(operator);
        boolean inRange = (upperLimit ? comparison < 0 : comparison > 0)
            || (comparison == 0 && operator.matches("[≤≥]|[<>]="));
        return inRange ? NORMAL : ABNORMAL;
    }

    static String reportedStatus(String rawFlag, String quote) {
        String flag = normalize(rawFlag).toUpperCase(Locale.ROOT);
        if (flag.isEmpty() || !quote.contains(rawFlag)) return UNKNOWN;
        // 文字标记须完整出现，避免从 U/L 或「未见异常」中截取异常标记。
        if (!flag.matches("[↑↓]+") && !Pattern.compile("(?<![\\p{L}/])" + Pattern.quote(rawFlag) + "(?![\\p{L}/])")
            .matcher(quote).find()) return UNKNOWN;
        if (flag.matches("H|L|↑+|↓+|异常|偏高|偏低|升高|降低|高于参考范围|低于参考范围")) return ABNORMAL;
        return flag.matches("正常|未见异常|无异常|范围内|在参考范围内") ? NORMAL : UNKNOWN;
    }

    private static String normalize(String text) {
        return Normalizer.normalize(text, Normalizer.Form.NFKC).replace('−','-').trim();
    }
}
