package com.example.website.prompt.service;

import com.example.website.prompt.model.PromptSource;
import com.example.website.prompt.model.PromptSourceSnapshot;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 提示词来源的内存快照服务，维护白名单里每个来源的最近一次结果。
 *
 * <p>快照存在 {@link LinkedHashMap} 里，顺序与注册表一致；读写方法都加 {@code synchronized}，
 * 因为刷新会替换共享 Map 中的条目。容器启动时先用注册表的内置摘要填充，所以第一次刷新之前
 * 列表接口也能返回稳定内容。</p>
 *
 * <p>刷新逐条串行处理：白名单外的 id 直接生成 {@code status=failed} 快照；抓取或摘要抛
 * {@link RuntimeException} 时退回内置摘要并保留失败原因。整个过程不向调用方抛异常，
 * 单个来源失败不会影响其他来源。来源数量固定为 6 个，串行抓取的代价可以接受。</p>
 */
@Service
public class PromptSourceFetchService {

    private final PromptSourceRegistry registry;
    private final PromptSourceSummaryService summaryService;
    private final PromptSourceHttpClient httpClient;
    /** 按来源 id 缓存的最近快照，键顺序与白名单一致；仅在构造器与 {@link #refresh} 中写入，读取统一走 {@link #listSnapshots()}。 */
    private final Map<String, PromptSourceSnapshot> snapshots = new LinkedHashMap<String, PromptSourceSnapshot>();

    /**
     * 生产构造器：注入注册表、摘要服务和抓取客户端，并用内置摘要初始化所有来源。
     *
     * @param registry       来源白名单，决定快照的键与顺序
     * @param summaryService 页面摘要生成器
     * @param httpClient     抓取实现，生产环境为 {@link DefaultPromptSourceHttpClient}
     */
    @Autowired
    public PromptSourceFetchService(PromptSourceRegistry registry,
                                    PromptSourceSummaryService summaryService,
                                    PromptSourceHttpClient httpClient) {
        this.registry = registry;
        this.summaryService = summaryService;
        this.httpClient = httpClient;
        for (PromptSource source : registry.listSources()) {
            snapshots.put(source.getId(), registry.defaultSnapshot(source.getId()));
        }
    }

    /**
     * 测试用构造器：把抓取客户端换成任何调用都会抛 {@link IllegalStateException} 的离线实现，
     * 因此用它构造的服务永远只返回内置摘要，不会联网。
     *
     * @param registry 来源白名单
     */
    public PromptSourceFetchService(PromptSourceRegistry registry) {
        this(registry, new PromptSourceSummaryService(), url -> {
            throw new IllegalStateException("offline test client");
        });
    }

    /**
     * 按注册表顺序返回当前快照。
     *
     * @return 每个白名单来源一条快照；缓存里缺失的键会用内置摘要即时补齐，因此结果长度恒等于
     *         白名单大小，不会抛异常
     */
    public synchronized List<PromptSourceSnapshot> listSnapshots() {
        List<PromptSourceSnapshot> result = new ArrayList<PromptSourceSnapshot>();
        for (PromptSource source : registry.listSources()) {
            PromptSourceSnapshot snapshot = snapshots.get(source.getId());
            result.add(snapshot == null ? registry.defaultSnapshot(source.getId()) : snapshot);
        }
        return result;
    }

    /**
     * 抓取指定来源并更新内存快照。
     *
     * <p>有副作用：会对外发起 HTTP 请求，并替换缓存中对应来源的快照。执行期间持有对象锁，
     * 并发的两个刷新请求会串行完成。</p>
     *
     * @param sourceIds 要刷新的来源 id；为 {@code null} 或空列表时刷新全部白名单来源
     * @return 与入参顺序一致的只读快照列表；未知 id 对应 {@code status=failed} 的快照，
     *         抓取失败的来源对应 {@code status=fallback} 且 {@code message} 带失败原因
     */
    public synchronized List<PromptSourceSnapshot> refresh(List<String> sourceIds) {
        List<String> ids = sourceIds;
        if (ids == null || ids.isEmpty()) {
            ids = new ArrayList<String>();
            for (PromptSource source : registry.listSources()) {
                ids.add(source.getId());
            }
        }

        List<PromptSourceSnapshot> result = new ArrayList<PromptSourceSnapshot>();
        for (String sourceId : ids) {
            PromptSource source = registry.findSource(sourceId);
            if (source == null) {
                result.add(registry.defaultSnapshot(sourceId));
                continue;
            }
            PromptSourceSnapshot snapshot = refreshAllowedSource(source);
            snapshots.put(source.getId(), snapshot);
            result.add(snapshot);
        }
        return Collections.unmodifiableList(result);
    }

    /**
     * 抓取单个白名单来源，成功时生成 {@code live} 快照，失败时降级。
     *
     * <p>降级不会重新抛出异常：会取内置摘要，并把 {@code message} 改成
     * {@code Live fetch failed: <原因>. Using built-in source summary.}，让页面能说明为什么看到的是
     * 摘要而不是实时内容。</p>
     *
     * @param source 已确认在白名单内的来源定义
     * @return 成功为 {@code live} 快照，失败为 {@code fallback} 快照；都不为 {@code null}
     */
    private PromptSourceSnapshot refreshAllowedSource(PromptSource source) {
        try {
            String content = httpClient.fetch(source.getUrl());
            String summary = summaryService.summarize(content);
            return new PromptSourceSnapshot(
                    source.getId(),
                    source.getName(),
                    source.getUrl(),
                    source.getType(),
                    source.getTags(),
                    "live",
                    summary,
                    java.time.OffsetDateTime.now(),
                    "Live source fetched.");
        } catch (RuntimeException exception) {
            PromptSourceSnapshot fallback = registry.defaultSnapshot(source.getId());
            fallback.setMessage("Live fetch failed: " + exception.getMessage() + ". Using built-in source summary.");
            return fallback;
        }
    }
}
