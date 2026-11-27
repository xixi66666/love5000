package com.example.website.prompt.service;

/**
 * 抓取来源页面的最小契约。
 *
 * <p>抽象成接口是为了让刷新逻辑能在单元测试里换成不联网的实现（见
 * {@code PromptSourceFetchService} 的测试构造器）；生产实现是
 * {@link DefaultPromptSourceHttpClient}。</p>
 */
public interface PromptSourceHttpClient {

    /**
     * 读取来源地址的文本内容。
     *
     * @param url 白名单来源地址，调用方已保证不会传入任意 URL
     * @return 页面文本；实现可对空响应做归一化
     * @throws RuntimeException 网络不可达、HTTP 非 2xx 等情况由实现抛出，调用方负责降级
     */
    String fetch(String url);
}
