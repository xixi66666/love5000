package com.example.personalagent.service;

import com.example.common.ai.ModelRoutingClient;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;

/**
 * 读取顶部栏模型选择器当前生效的模型（{@code provider:model}）。
 *
 * <p>属服务层的薄适配器，把 {@link ModelRoutingClient} 的失败收敛成空串：网关未启动、
 * 选择文件缺失或任何运行时异常都视为「没有统一选择」，由 {@link LocalDocuments}
 * 回退到服务原配置。因此这里的异常永不冒泡，页面不会因为模型选择器不可用而无法导入
 * 资料。</p>
 *
 * <p>本类不做缓存：每次调用都重新读选择状态，保证顶部栏切换后下一次导入立即生效，
 * 代价是一次轻量的本地文件读取。</p>
 */
@Service
public class ModelRoute {
    private final ObjectMapper json;

    public ModelRoute(ObjectMapper json) {
        this.json = json;
    }

    /**
     * 查询指定服务的生效模型。
     *
     * @param service 服务标识，个人资料库固定为 {@code personal-agent}
     * @return {@code provider:model}；没有选择或网关不可用时返回空串
     */
    public String current(String service) {
        try {
            return new ModelRoutingClient(json).effectiveModel(service);
        } catch (RuntimeException unavailable) {
            return "";
        }
    }
}
