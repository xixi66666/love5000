package com.example.website.prompt.controller;

import com.example.website.prompt.dto.PromptComposeRequest;
import com.example.website.prompt.dto.PromptSourceRefreshRequest;
import com.example.website.prompt.model.PromptVariant;
import com.example.website.prompt.service.PromptComposeService;
import com.example.website.prompt.service.PromptSourceFetchService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 旧版提示词控制台的 REST 接口：来源列表、来源刷新和提示词模板拼装。
 *
 * <p>这三个接口只做模板拼装与来源摘要，不读写数据库；来源白名单在
 * {@link com.example.website.prompt.service.PromptSourceRegistry}，快照与降级在
 * {@code PromptSourceFetchService}，拼装规则在 {@code PromptComposeService}。它与
 * {@code prompt.library} 下的 {@code /api/prompts} 系列库接口是两套独立功能：
 * 这里生成候选文案，库接口管理持久化数据。</p>
 *
 * <p>非显然行为：刷新接口会真实访问外部站点，单个来源失败不会让请求失败，而是把该来源换成内置
 * 摘要并在 {@code message} 里说明原因；拼装接口在场景为空时返回 {@code success=false}，
 * 但 HTTP 状态码仍是 200。</p>
 */
@RestController
@RequestMapping("/api")
public class PromptConsoleController {

    private final PromptSourceFetchService fetchService;
    private final PromptComposeService composeService;

    public PromptConsoleController(PromptSourceFetchService fetchService, PromptComposeService composeService) {
        this.fetchService = fetchService;
        this.composeService = composeService;
    }

    /**
     * 返回当前来源快照，不触发抓取。
     *
     * @return {@code {"success":true,"sources":[...]}}；未刷新过的来源为 {@code status=fallback}
     *         的内置摘要，条目顺序与白名单一致
     */
    @GetMapping("/prompt-sources")
    public Map<String, Object> listSources() {
        Map<String, Object> response = new HashMap<String, Object>();
        response.put("success", true);
        response.put("sources", fetchService.listSnapshots());
        return response;
    }

    /**
     * 按请求来源刷新快照，会真实抓取外部页面。
     *
     * <p>请求体可整体省略（{@code required = false}），此时刷新全部白名单来源；
     * 部分来源失败只会降级为内置摘要，响应仍是 {@code success=true}，失败原因在
     * 对应条目的 {@code message} 里。</p>
     *
     * @param request 可空的请求体，{@code sourceIds} 为空表示全部来源
     * @return {@code {"success":true,"sources":[...]}}，其中 sources 是刷新后的快照
     */
    @PostMapping("/prompt-sources/refresh")
    public Map<String, Object> refreshSources(@RequestBody(required = false) PromptSourceRefreshRequest request) {
        Map<String, Object> response = new HashMap<String, Object>();
        response.put("success", true);
        response.put("sources", fetchService.refresh(request == null ? null : request.getSourceIds()));
        return response;
    }

    /**
     * 按场景拼装多个候选提示词版本。
     *
     * @param request 拼装请求，{@code scene} 必填；缺省时由服务抛
     *                {@link IllegalArgumentException} 并在这里转成业务错误
     * @return 成功为 {@code {"success":true,"results":[...]}}；场景为空时为
     *         {@code {"success":false,"message":"场景不能为空"}}，HTTP 状态仍为 200
     */
    @PostMapping("/prompts/compose")
    public Map<String, Object> compose(@RequestBody PromptComposeRequest request) {
        Map<String, Object> response = new HashMap<String, Object>();
        try {
            List<PromptVariant> variants = composeService.compose(request);
            response.put("success", true);
            response.put("results", variants);
            return response;
        } catch (IllegalArgumentException exception) {
            response.put("success", false);
            response.put("message", exception.getMessage());
            return response;
        }
    }
}
