package com.example.personalagent.service;

import com.example.common.ai.ModelRoutingClient;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;

/**
 * 读取顶部栏模型选择器当前生效的模型（provider:model）。
 * 网关不可用或未启用统一选择时返回空串，调用方回退到服务原配置。
 */
@Service
public class ModelRoute {
    private final ObjectMapper json;

    public ModelRoute(ObjectMapper json) {
        this.json = json;
    }

    public String current(String service) {
        try {
            return new ModelRoutingClient(json).effectiveModel(service);
        } catch (RuntimeException unavailable) {
            return "";
        }
    }
}
