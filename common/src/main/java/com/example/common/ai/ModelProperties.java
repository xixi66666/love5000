package com.example.common.ai;

import java.io.BufferedReader;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Properties;
import java.util.Set;

/**
 * 项目根目录 model.properties 的唯一读取入口。
 *
 * <p>所有服务共用这一个本地文件：提供商地址、密钥、模型目录和服务原配置都在这里。
 * 文件不入库，只按目录层次查找，不读取任何模型相关环境变量。</p>
 */
public final class ModelProperties {

    public static final String FILE_NAME = "model.properties";
    public static final String GLOBAL_SCOPE = "global";

    /** 一个模型提供商，例如 deepseek、mimo、image。 */
    public static final class Provider {
        private final String id;
        private final String label;
        private final String baseUrl;
        private final String apiKey;
        private final String capability;
        private final List<String> models;
        private final Map<String, String> options;

        Provider(String id, String label, String baseUrl, String apiKey, String capability,
                 List<String> models, Map<String, String> options) {
            this.id = id;
            this.label = label;
            this.baseUrl = baseUrl;
            this.apiKey = apiKey;
            this.capability = capability;
            this.models = Collections.unmodifiableList(models);
            this.options = Collections.unmodifiableMap(options);
        }

        public String id() { return id; }
        public String label() { return label; }
        public String baseUrl() { return baseUrl; }
        public String apiKey() { return apiKey; }
        public String capability() { return capability; }
        public List<String> models() { return models; }

        public boolean text() { return "text".equals(capability); }

        public String option(String name) { return options.getOrDefault(name, "").trim(); }

        public String option(String name, String fallback) {
            String value = option(name);
            return value.isEmpty() ? fallback : value;
        }

        public int intOption(String name, int fallback) {
            String value = option(name);
            if (value.isEmpty()) return fallback;
            try { return Integer.parseInt(value); } catch (NumberFormatException ignored) { return fallback; }
        }

        public List<String> optionList(String name) {
            return splitList(option(name));
        }
    }

    /** 某服务的原配置：提供商 + 模型。 */
    public static final class Route {
        private final Provider provider;
        private final String modelId;

        Route(Provider provider, String modelId) {
            this.provider = provider;
            this.modelId = modelId;
        }

        public Provider provider() { return provider; }
        public String modelId() { return modelId; }
        public String id() { return provider.id() + ":" + modelId; }
    }

    private final Path file;
    private final boolean exists;
    private final Map<String, Provider> providers;
    private final Map<String, String> routes;

    private ModelProperties(Path file, boolean exists, Map<String, Provider> providers, Map<String, String> routes) {
        this.file = file;
        this.exists = exists;
        this.providers = Collections.unmodifiableMap(providers);
        this.routes = Collections.unmodifiableMap(routes);
    }

    public Path file() { return file; }
    public boolean exists() { return exists; }
    public Provider provider(String id) { return id == null ? null : providers.get(id.trim().toLowerCase(Locale.ROOT)); }
    public Collection<Provider> providers() { return providers.values(); }

    public List<Provider> textProviders() {
        List<Provider> list = new ArrayList<Provider>();
        for (Provider provider : providers.values()) if (provider.text()) list.add(provider);
        return list;
    }

    /** 解析服务原配置；未单独指定时回退 global。 */
    public Route route(String scope) {
        Route route = parseRoute(routes.get(scope));
        if (route == null && !GLOBAL_SCOPE.equals(scope)) route = parseRoute(routes.get(GLOBAL_SCOPE));
        return route;
    }

    private Route parseRoute(String raw) {
        if (raw == null) return null;
        String value = raw.trim();
        if (value.isEmpty()) return null;
        int split = value.indexOf(':');
        if (split <= 0 || split == value.length() - 1) return null;
        Provider provider = provider(value.substring(0, split));
        if (provider == null) return null;
        return new Route(provider, value.substring(split + 1).trim());
    }

    public static Path locate() {
        return locate(Paths.get("").toAbsolutePath());
    }

    public static Path locate(Path start) {
        Path current = start == null ? Paths.get("").toAbsolutePath() : start.toAbsolutePath().normalize();
        for (Path candidate = current; candidate != null; candidate = candidate.getParent()) {
            Path file = candidate.resolve(FILE_NAME);
            if (Files.isRegularFile(file)) return file;
        }
        return current.resolve(FILE_NAME);
    }

    public static ModelProperties load() {
        return load(locate());
    }

    public static ModelProperties load(Path file) {
        Path path = file == null ? locate() : file.toAbsolutePath().normalize();
        boolean exists = Files.isRegularFile(path);
        LinkedHashMap<String, Provider> providers = new LinkedHashMap<String, Provider>();
        LinkedHashMap<String, String> routes = new LinkedHashMap<String, String>();
        if (!exists) return new ModelProperties(path, false, providers, routes);

        OrderedProperties properties = new OrderedProperties();
        try (BufferedReader reader = openReader(path)) {
            properties.load(reader);
        } catch (IOException e) {
            throw new IllegalStateException("无法读取模型配置：" + path, e);
        }

        LinkedHashMap<String, Map<String, String>> groups = new LinkedHashMap<String, Map<String, String>>();
        for (String name : properties.keyOrder()) {
            String id = providerId(name);
            if (id != null) groups.put(id, new LinkedHashMap<String, String>());
        }
        for (String name : properties.stringPropertyNames()) {
            String key = name.trim();
            if (key.isEmpty()) continue;
            if (key.startsWith("service.")) {
                String scope = key.substring("service.".length()).trim().toLowerCase(Locale.ROOT);
                String value = properties.getProperty(name, "").trim();
                if (!scope.isEmpty() && !value.isEmpty()) routes.put(scope, value);
                continue;
            }
            String id = providerId(name);
            if (id == null) continue;
            int dot = key.indexOf('.');
            String field = key.substring(dot + 1).trim().toLowerCase(Locale.ROOT);
            if (field.isEmpty()) continue;
            Map<String, String> group = groups.get(id);
            if (group == null) { group = new LinkedHashMap<String, String>(); groups.put(id, group); }
            group.put(field, properties.getProperty(name, "").trim());
        }

        for (Map.Entry<String, Map<String, String>> entry : groups.entrySet()) {
            String id = entry.getKey();
            Map<String, String> values = entry.getValue();
            String baseUrl = values.getOrDefault("base-url", "").replaceAll("/+$", "");
            if (baseUrl.isEmpty()) continue;
            String label = values.getOrDefault("label", id);
            String apiKey = values.getOrDefault("api-key", "");
            String capability = values.getOrDefault("capability", "text");
            if (capability.isEmpty()) capability = "text";
            List<String> models = splitList(values.getOrDefault("models", ""));
            LinkedHashMap<String, String> options = new LinkedHashMap<String, String>(values);
            options.remove("label"); options.remove("base-url"); options.remove("api-key");
            options.remove("capability"); options.remove("models");
            providers.put(id, new Provider(id, label, baseUrl, apiKey, capability.trim(),
                    models, options));
        }
        return new ModelProperties(path, true, providers, routes);
    }

    private static BufferedReader openReader(Path path) throws IOException {
        BufferedReader reader = Files.newBufferedReader(path, StandardCharsets.UTF_8);
        reader.mark(1);
        if (reader.read() != '\uFEFF') {
            reader.reset();
        }
        return reader;
    }

    private static String providerId(String name) {
        String key = name.trim();
        if (key.isEmpty() || key.startsWith("service.")) return null;
        int dot = key.indexOf('.');
        if (dot <= 0) return null;
        String id = key.substring(0, dot).trim().toLowerCase(Locale.ROOT);
        return id.isEmpty() ? null : id;
    }

    /** 记录键首次进入 Properties 的顺序，供展示顺序使用。 */
    private static final class OrderedProperties extends Properties {
        private static final long serialVersionUID = 1L;
        private final Set<String> keys = new LinkedHashSet<String>();

        @Override
        public synchronized Object put(Object key, Object value) {
            if (key instanceof String) keys.add((String) key);
            return super.put(key, value);
        }

        List<String> keyOrder() {
            return new ArrayList<String>(keys);
        }
    }

    static List<String> splitList(String raw) {
        List<String> values = new ArrayList<String>();
        if (raw == null) return values;
        for (String part : raw.split(",")) {
            String value = part.trim();
            if (!value.isEmpty() && !values.contains(value)) values.add(value);
        }
        return values;
    }
}
