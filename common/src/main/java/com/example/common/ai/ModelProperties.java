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
 * 项目根目录 {@code model.properties} 的唯一读取入口。
 *
 * <p>所有服务共用这一个本地文件：提供商地址、密钥、模型目录和服务原配置都在这里。
 * 文件不入库，只按目录层次查找，不读取任何模型相关环境变量。</p>
 *
 * <p>查找规则见 {@link #locate(Path)}：从给定目录开始逐级向上查找同名文件，找不到时返回
 * 起始目录下的默认路径。文件缺失不算错误——{@link #exists()} 返回 {@code false}，
 * 提供商目录为空、路由为 {@code null}，调用方据此退化到自身原配置；只有文件存在但读取失败
 * 才会抛出 {@code IllegalStateException}。</p>
 *
 * <p>解析是宽松的：{@code base-url} 缺失的提供商整组忽略，{@code service.*} 中无法解析成
 * 「已知提供商:模型」的值也静默丢弃，不会因为一行写错就让整个服务起不来。
 * 提供商按首次出现的顺序保留，便于选择界面稳定展示。</p>
 */
public final class ModelProperties {

    /** 配置文件固定名称；查找时按此名从当前目录逐级向上匹配。 */
    public static final String FILE_NAME = "model.properties";
    /** 全局兜底路由的作用域名；某个服务没有单独配置时回退到这里。 */
    public static final String GLOBAL_SCOPE = "global";

    /**
     * 一个模型提供商的不可变快照，例如 deepseek、mimo、image。
     *
     * <p>字段全部来自配置文件：{@code label} 是展示名（缺省回落到 id），{@code capability}
     * 区分文本与其他能力，{@code models} 是可选模型清单；其余键（如 {@code tts-model}、
     * {@code image-model}）原样保存在 {@code options} 中，供各业务按需读取。</p>
     */
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

        /**
         * 读取附加配置项并去掉首尾空格；缺失时返回空串而不是 {@code null}。
         *
         * @param name 键名，例如 {@code tts-model}
         * @return 配置值，缺失时为空串
         */
        public String option(String name) { return options.getOrDefault(name, "").trim(); }

        /**
         * 读取附加配置项，缺失或为空白时返回调用方给定的默认值。
         *
         * @param name 键名
         * @param fallback 缺失时的默认值
         * @return 配置值或默认值
         */
        public String option(String name, String fallback) {
            String value = option(name);
            return value.isEmpty() ? fallback : value;
        }

        /**
         * 读取整数配置项；缺失或不是合法整数时返回默认值，不抛异常。
         *
         * @param name 键名
         * @param fallback 缺失或解析失败时的默认值
         * @return 解析出的整数或默认值
         */
        public int intOption(String name, int fallback) {
            String value = option(name);
            if (value.isEmpty()) return fallback;
            try { return Integer.parseInt(value); } catch (NumberFormatException ignored) { return fallback; }
        }

        /**
         * 读取逗号分隔的配置项并拆成列表。
         *
         * @param name 键名
         * @return 去重后的列表，缺失时为空列表
         */
        public List<String> optionList(String name) {
            return splitList(option(name));
        }
    }

    /**
     * 某服务的原配置：提供商与模型 ID 的组合。
     *
     * <p>由 {@code service.<scope>=<provider>:<model>} 解析而来，{@link #id()} 以
     * {@code provider:model} 形式回写，便于与配置文件、选择状态文件对照排查。</p>
     */
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

    /** 实际使用的配置文件路径；文件不存在时仍保留预期路径，便于错误提示。 */
    private final Path file;
    /** 文件是否真实存在；为 {@code false} 时提供商与路由均为空，且不抛异常。 */
    private final boolean exists;
    /** 提供商目录，键为小写 id，顺序与配置文件中的首次出现顺序一致。 */
    private final Map<String, Provider> providers;
    /** 服务级原配置，键为小写服务标识，值为尚未解析的 provider:model 原文。 */
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

    /**
     * 只保留 {@code capability} 为 {@code text} 的提供商，用于文本模型选择。
     *
     * @return 按配置顺序排列的文本提供商列表，可能为空
     */
    public List<Provider> textProviders() {
        List<Provider> list = new ArrayList<Provider>();
        for (Provider provider : providers.values()) if (provider.text()) list.add(provider);
        return list;
    }

    /**
     * 解析服务原配置。
     *
     * <p>先查 {@code service.<scope>}，缺失或无法解析时回退到 {@code service.global}；
     * 两者都不可用时返回 {@code null}，调用方应继续使用自身的原配置。</p>
     *
     * @param scope 服务标识，例如 {@code python-a}、{@code personal-agent}
     * @return 已解析的路由，无法解析时为 {@code null}
     */
    public Route route(String scope) {
        Route route = parseRoute(routes.get(scope));
        if (route == null && !GLOBAL_SCOPE.equals(scope)) route = parseRoute(routes.get(GLOBAL_SCOPE));
        return route;
    }

    /**
     * 把 {@code provider:model} 原文解析成路由。
     *
     * <p>冒号必须出现在中间且两侧都非空，提供商必须已在目录中；任何不满足的情况都返回
     * {@code null} 而不是抛异常，对应配置写错时只影响该服务自己。</p>
     *
     * @param raw 配置原文，可为 {@code null}
     * @return 解析成功时的路由，否则为 {@code null}
     */
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

    /**
     * 以当前工作目录为起点查找配置文件。
     *
     * @return 实际找到的文件路径，或起始目录下的默认路径（可能不存在）
     */
    public static Path locate() {
        return locate(Paths.get("").toAbsolutePath());
    }

    /**
     * 从起始目录逐级向上查找 {@code model.properties}。
     *
     * <p>只依据文件系统层次，不读取任何环境变量，因此从子模块目录启动也能找到仓库根目录的
     * 配置文件；一路到根都没有时返回起始目录下的默认路径，由调用方按「文件不存在」处理。</p>
     *
     * @param start 起始目录，{@code null} 表示当前工作目录
     * @return 找到的文件路径，或起始目录下的默认路径
     */
    public static Path locate(Path start) {
        Path current = start == null ? Paths.get("").toAbsolutePath() : start.toAbsolutePath().normalize();
        for (Path candidate = current; candidate != null; candidate = candidate.getParent()) {
            Path file = candidate.resolve(FILE_NAME);
            if (Files.isRegularFile(file)) return file;
        }
        return current.resolve(FILE_NAME);
    }

    /**
     * 从当前位置向上查找到的文件加载配置。
     *
     * @return 配置快照；文件不存在时返回空目录且 {@code exists} 为 {@code false}
     */
    public static ModelProperties load() {
        return load(locate());
    }

    /**
     * 加载指定配置文件。
     *
     * <p>只保留 {@code label}、{@code base-url}、{@code api-key}、{@code capability}、
     * {@code models} 五个保留键，其余键进入 {@code options}；{@code capability} 缺省为
     * {@code text}，{@code base-url} 为空的提供商整组丢弃。返回的对象是不可变快照。</p>
     *
     * @param file 配置文件路径，{@code null} 表示自动查找
     * @return 配置快照；文件不存在时返回空目录而非抛异常
     * @throws IllegalStateException 文件存在但读取失败时抛出
     */
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

    /**
     * 以 UTF-8 打开文件并跳过 BOM。
     *
     * <p>带 BOM 的配置文件若不过滤，首个键名会含不可见字符，导致第一个提供商被静默丢弃；
     * 因此先探测首字符，不是 BOM 再回退读取位置。</p>
     *
     * @param path 配置文件路径
     * @return 定位到文件头的读取器，由调用方负责关闭
     * @throws IOException 打开失败时抛出
     */
    private static BufferedReader openReader(Path path) throws IOException {
        BufferedReader reader = Files.newBufferedReader(path, StandardCharsets.UTF_8);
        reader.mark(1);
        if (reader.read() != '\uFEFF') {
            reader.reset();
        }
        return reader;
    }

    /**
     * 从键名中提取提供商 id。
     *
     * <p>{@code service.*} 行、没有点号的键以及空键都返回 {@code null}，表示不属于任何提供商。</p>
     *
     * @param name 原始键名
     * @return 小写提供商 id，或 {@code null}
     */
    private static String providerId(String name) {
        String key = name.trim();
        if (key.isEmpty() || key.startsWith("service.")) return null;
        int dot = key.indexOf('.');
        if (dot <= 0) return null;
        String id = key.substring(0, dot).trim().toLowerCase(Locale.ROOT);
        return id.isEmpty() ? null : id;
    }

    /**
     * 记录键首次进入 {@code Properties} 的顺序，供展示排序使用。
     *
     * <p>{@code Properties} 本身是无序的，这里在 {@code put} 时旁路记录首次出现的键名，
     * 因此同一键被覆盖不会改变顺序；键集合只用于遍历，不参与取值。</p>
     */
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

    /**
     * 按逗号拆分列表：去首尾空格、丢弃空项、去重并保持首次出现的顺序。
     *
     * @param raw 逗号分隔的原文，可为 {@code null}
     * @return 去重后的字符串列表，可能为空
     */
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
