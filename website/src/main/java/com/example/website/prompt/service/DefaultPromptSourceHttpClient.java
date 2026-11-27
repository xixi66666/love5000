package com.example.website.prompt.service;

import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

/**
 * 基于 {@link RestTemplate} 的来源抓取实现，是 {@link PromptSourceHttpClient} 的生产实现。
 *
 * <p>只做“取文本 + 截断”：响应超过 120000 字符就截断，避免把整页 HTML 都交给摘要处理；
 * 空响应归一化为空串。这里没有显式设置连接/读取超时，沿用 {@code new RestTemplate()} 的默认行为，
 * 刷新是人工触发的低频操作，且调用方会把超时与异常降级为内置摘要。</p>
 */
@Component
public class DefaultPromptSourceHttpClient implements PromptSourceHttpClient {

    private final RestTemplate restTemplate = new RestTemplate();

    /**
     * 以 GET 读取来源页面。
     *
     * @param url 白名单来源地址
     * @return 响应正文；空响应返回 {@code ""}，超长截断到 120000 字符
     * @throws RuntimeException 网络异常或 HTTP 非 2xx 时由 {@link RestTemplate} 抛出，
     *                          由 {@code PromptSourceFetchService} 捕获并降级
     */
    @Override
    public String fetch(String url) {
        String body = restTemplate.getForObject(url, String.class);
        if (body == null) {
            return "";
        }
        if (body.length() > 120000) {
            return body.substring(0, 120000);
        }
        return body;
    }
}
