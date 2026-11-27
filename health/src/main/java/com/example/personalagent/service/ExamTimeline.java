package com.example.personalagent.service;

import com.fasterxml.jackson.databind.JsonNode;

import java.math.BigDecimal;
import java.text.Normalizer;
import java.time.LocalDate;
import java.util.*;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

import static com.example.personalagent.Api.*;

/** 从有原件依据的草稿生成跨次关联，保留各次检查及其独立证据。 */
final class ExamTimeline {
    private static final Pattern DECIMAL = Pattern.compile("[+-]?\\d{1,12}(?:\\.\\d{1,8})?");
    private static final Map<String,String> METRIC_ALIASES = aliases();
    private static final Map<String,Pattern> TOPICS = topics();
    private final List<Map<String,Object>> exams = new ArrayList<>();
    private final Map<List<String>,List<Map<String,Object>>> metrics = new LinkedHashMap<>();
    private final List<Map<String,Object>> individualMetrics = new ArrayList<>();
    private final Map<String,List<Map<String,Object>>> observations = new LinkedHashMap<>();
    private int verifiedExamCount;

    void add(String id, String date, String sourcePath, JsonNode findings) {
        if (!date.matches("\\d{4}-\\d{2}-\\d{2}")) return;
        try { LocalDate.parse(date); }
        catch (java.time.DateTimeException invalid) { return; }
        boolean verified = findings.path("textEvidenceVerified").asBoolean(false);
        boolean pageVerified = findings.path("pdfPageEvidenceVerified").asBoolean(false);
        exams.add(map("exam_id",id,"date",date,"source_path",sourcePath,"verified",verified));
        if (!verified) return;
        verifiedExamCount++;

        Map<List<String>,List<Map<String,Object>>> examMetrics = new LinkedHashMap<>();
        for (JsonNode row : findings.path("metrics")) {
            String name = field(row,"name"), originalUnit = field(row,"unit");
            String value = field(row,"value"), quote = field(row,"quote");
            if (name.isEmpty() || value.isEmpty() || !quote.contains(name)
                || !quote.contains(value) || !quote.contains(originalUnit)) continue;
            String normalizedName = normalizeName(name);
            String label = METRIC_ALIASES.getOrDefault(normalizedName,name);
            String unit = normalizeUnit(originalUnit);
            BigDecimal number = DECIMAL.matcher(value).matches() ? new BigDecimal(value) : null;
            Map<String,Object> point = point(id,date,row,pageVerified);
            String flag = literalField(row, "flag", quote);
            point.putAll(map("name",name,"value",value,"number",number,"unit",originalUnit,
                "label",label,"range",literalField(row,"range",quote),"flag",flag,"status",field(row,"status"),
                "marked",ExamMetricStatus.ABNORMAL.equals(ExamMetricStatus.reportedStatus(flag,quote))));
            if (row.has("external_reference")) point.put("external_reference",row.get("external_reference"));
            if (row.path("range_recovered").asBoolean()) point.put("range_recovered",true);
            JsonNode standard = row.path("standardization");
            String loinc = field(standard,"loinc"), comparisonUnit = field(standard,"comparison_unit");
            BigDecimal comparisonNumber = decimal(field(standard,"comparison_value"));
            if (standard.isObject()) point.put("standardization",standard);
            boolean codedComparison = loinc.matches("\\d+-\\d") && !comparisonUnit.isEmpty() && number != null && comparisonNumber != null;
            boolean comparableValue = number != null || ("血压".equals(label) && "mmHg".equals(unit) && value.matches("\\d{2,3}/\\d{2,3}"));
            if (unit.isEmpty() || !comparableValue || (standard.isObject() && !codedComparison)) {
                individualMetrics.add(point);
                continue;
            }
            List<String> key;
            if (codedComparison) {
                key = Arrays.asList("loinc:"+loinc,comparisonUnit);
                point.put("comparison_number",comparisonNumber);
            } else {
                key = Arrays.asList(METRIC_ALIASES.getOrDefault(normalizedName,normalizedName),unit);
            }
            examMetrics.computeIfAbsent(key, unused -> new ArrayList<>()).add(point);
        }
        for (Map.Entry<List<String>,List<Map<String,Object>>> entry : examMetrics.entrySet()) {
            // 同一检查中有多个候选时，不能代替用户判断是哪一个标本或测量条件。
            if (entry.getValue().size() == 1) {
                metrics.computeIfAbsent(entry.getKey(),unused -> new ArrayList<>()).add(entry.getValue().get(0));
            } else {
                individualMetrics.addAll(entry.getValue());
            }
        }
        Set<List<String>> seen = new HashSet<>();
        for (JsonNode row : findings.path("observations")) {
            String quote = field(row,"quote");
            if (quote.isEmpty()) continue;
            String normalizedQuote = compact(quote);
            for (Map.Entry<String,Pattern> topic : TOPICS.entrySet()) {
                if (!topic.getValue().matcher(normalizedQuote).find() || !seen.add(Arrays.asList(topic.getKey(),quote))) continue;
                observations.computeIfAbsent(topic.getKey(),unused -> new ArrayList<>()).add(point(id,date,row,pageVerified));
            }
        }
    }

    Map<String,Object> result() {
        Comparator<Map<String,Object>> byDate = Comparator.comparing((Map<String,Object> row) -> text(row,"date"))
            .thenComparing(row -> text(row,"exam_id"));
        exams.sort(byDate);
        List<Map<String,Object>> metricTracks = new ArrayList<>();
        for (Map.Entry<List<String>,List<Map<String,Object>>> entry : metrics.entrySet()) {
            List<Map<String,Object>> points = entry.getValue();
            if (!spansDates(points)) {
                individualMetrics.addAll(points);
                continue;
            }
            points.sort(byDate);
            Map<String,Object> first = points.get(0), last = points.get(points.size()-1);
            boolean uniqueDates = points.stream().map(point -> text(point,"date")).distinct().count() == points.size();
            boolean mixedUnits = points.stream().map(point -> normalizeUnit(text(point,"unit"))).distinct().limit(2).count() > 1;
            String numberField = mixedUnits ? "comparison_number" : "number";
            BigDecimal delta = uniqueDates && first.get(numberField) instanceof BigDecimal && last.get(numberField) instanceof BigDecimal
                ? ((BigDecimal) last.get(numberField)).subtract((BigDecimal) first.get(numberField)) : null;
            String unit = mixedUnits ? entry.getKey().get(1) : normalizeUnit(text(first,"unit"));
            metricTracks.add(map("label",first.get("label"),"unit",unit,"points",points,"status",trackStatus(points),
                "converted",mixedUnits,"loinc",entry.getKey().get(0).startsWith("loinc:") ? entry.getKey().get(0).substring(6) : null,
                "flagged_count",points.stream().filter(point -> Boolean.TRUE.equals(point.get("marked"))).count(),
                "change",delta == null ? null : delta.stripTrailingZeros().toPlainString()));
        }
        metricTracks.sort(Comparator.comparingLong((Map<String,Object> series) -> (long) series.get("flagged_count"))
            .reversed().thenComparing(series -> text(series,"label")));
        List<Map<String,Object>> topicTracks = observations.entrySet().stream()
            .filter(entry -> spansDates(entry.getValue()))
            .map(entry -> {
                entry.getValue().sort(byDate);
                return map("label",entry.getKey(),"points",entry.getValue());
            }).collect(Collectors.toList());
        individualMetrics.sort(byDate.reversed().thenComparing(point -> text(point,"name")));
        return map("reports",exams,"verified_report_count",verifiedExamCount,"metrics",metricTracks,
            "individual_metrics",individualMetrics,"topics",topicTracks);
    }

    private static String trackStatus(List<Map<String,Object>> points) {
        if (points.stream().anyMatch(point -> ExamMetricStatus.ABNORMAL.equals(point.get("status")))) return ExamMetricStatus.ABNORMAL;
        return points.stream().allMatch(point -> ExamMetricStatus.NORMAL.equals(point.get("status")))
            ? ExamMetricStatus.NORMAL : ExamMetricStatus.UNKNOWN;
    }

    private static boolean spansDates(List<Map<String,Object>> points) {
        return points.stream().map(point -> text(point,"date")).distinct().limit(2).count() == 2;
    }

    private static BigDecimal decimal(String value) {
        return value.matches("[+-]?\\d{1,14}(?:\\.\\d{1,14})?(?:[eE][+-]?\\d{1,2})?") ? new BigDecimal(value) : null;
    }

    private static Map<String,Object> point(String id, String date, JsonNode row, boolean pageVerified) {
        return map("exam_id",id,"date",date,"quote",field(row,"quote"),"location",field(row,"location"),"page_verified",pageVerified);
    }

    private static String literalField(JsonNode row, String key, String quote) {
        String value = field(row,key);
        return quote.contains(value) ? value : "";
    }

    private static String field(JsonNode row, String key) {
        JsonNode value = row.path(key);
        return value.isTextual() ? value.textValue().trim() : "";
    }

    private static String compact(String text) {
        return Normalizer.normalize(text, Normalizer.Form.NFKC).replaceAll("[\\p{Z}\\s]+", "");
    }

    private static String normalizeName(String name) {
        return compact(name).toUpperCase(Locale.ROOT);
    }

    private static String normalizeUnit(String unit) {
        String normalized = compact(unit).replace('μ','u').replaceAll("/l$", "/L");
        return "kg/m2".equals(normalized) ? "kg/m²" : normalized;
    }

    private static Map<String,String> aliases() {
        Map<String,String> names = new HashMap<>();
        addAliases(names,"红细胞压积","红细胞压积HCT","红细胞压积(HCT)","红细胞比容","红细胞比容(HCT)","HCT");
        addAliases(names,"尿酸","尿酸(UA)","UA");
        addAliases(names,"体质指数","BMI","体重指数","体质指数(BMI)","体重指数(BMI)");
        addAliases(names,"血压");
        addAliases(names,"血红蛋白","血红蛋白HGB","血红蛋白(HGB)","HGB");
        addAliases(names,"总胆固醇","总胆固醇(TC)","TC");
        return Collections.unmodifiableMap(names);
    }

    private static void addAliases(Map<String,String> names, String label, String... variants) {
        names.put(normalizeName(label),label);
        for (String variant : variants) names.put(normalizeName(variant),label);
    }

    private static Map<String,Pattern> topics() {
        Map<String,Pattern> patterns = new LinkedHashMap<>();
        patterns.put("肺结节", Pattern.compile("(?:左肺|右肺|双肺|两肺|肺内|肺部|肺.{0,3}叶)[^。；，、]{0,24}结节|肺结节"));
        patterns.put("肺部钙化灶", Pattern.compile("肺[^。；，、]{0,12}钙化灶"));
        patterns.put("肺部条索影", Pattern.compile("肺[^。；，、]{0,12}条索影"));
        patterns.put("眼底所见", Pattern.compile("眼底"));
        return Collections.unmodifiableMap(patterns);
    }
}
