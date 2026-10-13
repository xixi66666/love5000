package com.example.personalagent.finance;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.math.BigDecimal;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.Charset;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.time.format.ResolverStyle;
import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import static com.example.personalagent.Api.map;

/** Fixed Tencent endpoint, GBK tilde protocol; A-shares and exchange-traded ETFs only. */
public class QuoteProvider {
    public interface HttpClient { String get(String url) throws Exception; }
    private final HttpClient client;
    public QuoteProvider() { this(new RestrictedHttpClient()); }
    public QuoteProvider(HttpClient client) { this.client = client; }

    public static String normalizeSymbol(String value) {
        String symbol = value == null ? "" : value.trim().toLowerCase(Locale.ROOT);
        if (symbol.matches("\\d{6}")) {
            String prefix = symbol.startsWith("5") || symbol.startsWith("6") ? "sh"
                    : symbol.startsWith("4") || symbol.startsWith("8") || symbol.startsWith("920") ? "bj" : "sz";
            symbol = prefix + symbol;
        }
        if (!symbol.matches("(?:sh[56]\\d{5}|sz[013]\\d{5}|bj[489]\\d{5})")) {
            throw new IllegalArgumentException("仅支持明确的 A 股和沪深场内 ETF 代码");
        }
        return symbol;
    }

    public Map<String, Map<String, Object>> fetch(List<String> requested) {
        Set<String> unique = new LinkedHashSet<>();
        for (String value : requested) unique.add(normalizeSymbol(value));
        if (unique.size() > 100) throw new IllegalArgumentException("每次最多刷新 100 个标的");
        if (unique.isEmpty()) return new LinkedHashMap<>();
        try {
            String url = "https://qt.gtimg.cn/q=" + String.join(",", unique);
            return parse(client.get(url), unique);
        } catch (Exception exception) {
            // Never propagate an HTTP error that might contain headers or local proxy details.
            throw new IllegalStateException("行情来源暂时不可用，请稍后重试");
        }
    }

    public static Map<String, Map<String, Object>> parse(String payload, Collection<String> requested) {
        Map<String, Map<String, Object>> result = new LinkedHashMap<>();
        Matcher matcher = Pattern.compile("v_((?:sh|sz|bj)\\d{6})=\"([^\"\\r\\n]*)\"").matcher(payload == null ? "" : payload);
        while (matcher.find()) {
            String symbol = matcher.group(1);
            String[] fields = matcher.group(2).split("~", -1);
            if (!requested.contains(symbol) || fields.length < 31 || !fields[2].equals(symbol.substring(2))) continue;
            try {
                BigDecimal price = new BigDecimal(fields[3]);
                if (price.signum() <= 0 || price.compareTo(new BigDecimal("10000000")) > 0) continue;
                String previous = null;
                if (!fields[4].isEmpty()) {
                    BigDecimal close = new BigDecimal(fields[4]);
                    if (close.signum() > 0) previous = close.toPlainString();
                }
                String time = LocalDateTime.parse(fields[30], DateTimeFormatter.ofPattern("uuuuMMddHHmmss").withResolverStyle(ResolverStyle.STRICT))
                        .toInstant(ZoneOffset.ofHours(8)).toString();
                result.put(symbol, map("symbol", symbol, "price", price.toPlainString(), "previous_close", previous,
                        "currency", "CNY", "market_time", time, "source", "Tencent Finance", "status", "valid",
                        "source_url", "https://qt.gtimg.cn/q=" + symbol));
            } catch (RuntimeException ignored) {
                // Missing or invalid price/time is omitted rather than fabricated as zero.
            }
        }
        return result;
    }

    private static class RestrictedHttpClient implements HttpClient {
        @Override public String get(String url) throws Exception {
            if (!url.matches("https://qt\\.gtimg\\.cn/q=(?:(?:sh|sz|bj)\\d{6})(?:,(?:sh|sz|bj)\\d{6})*")) {
                throw new IllegalArgumentException("不允许自定义行情 URL");
            }
            HttpURLConnection connection = (HttpURLConnection) new URL(url).openConnection();
            connection.setConnectTimeout(10000);
            connection.setReadTimeout(10000);
            connection.setInstanceFollowRedirects(false);
            connection.setRequestProperty("User-Agent", "Mozilla/5.0");
            try {
                if (connection.getResponseCode() != 200) throw new IllegalStateException("行情来源不可用");
                try (InputStream input = connection.getInputStream(); ByteArrayOutputStream output = new ByteArrayOutputStream()) {
                    byte[] buffer = new byte[4096];
                    int size;
                    while ((size = input.read(buffer)) != -1) {
                        if (output.size() + size > 1024 * 1024) throw new IllegalStateException("行情响应过大");
                        output.write(buffer, 0, size);
                    }
                    return new String(output.toByteArray(), Charset.forName("GBK"));
                }
            } finally { connection.disconnect(); }
        }
    }
}
