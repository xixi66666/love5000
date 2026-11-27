package com.example.website.prompt.library.controller;

import com.example.website.prompt.library.dto.PromptCreateRequest;
import com.example.website.prompt.library.dto.PromptCreateResponse;
import com.example.website.prompt.library.dto.PromptDetailResponse;
import com.example.website.prompt.library.dto.PromptListResponse;
import com.example.website.prompt.library.dto.PromptMetaResponse;
import com.example.website.prompt.library.dto.PromptSearchRequest;
import com.example.website.prompt.library.service.PromptLibraryService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.Map;

/**
 * 提示词库 REST 控制器，对外暴露 {@code /api/prompts} 系列接口。
 *
 * <p>数据来自 MySQL {@code xixi} 库的 {@code prompt_entry}/{@code prompt_source}/{@code prompt_group}
 * 三张表。业务规则（分页纠正、LIKE 转义、详情映射、添加校验与大分类推导）全部在
 * {@link PromptLibraryService} 内，本类只做参数绑定、响应包装和异常到 HTTP 状态码的映射。</p>
 *
 * <p>非显然行为：列表接口用 {@link PromptSearchRequest} 承接查询串，{@code page}/{@code size}
 * 的缺省值来自 DTO，越界纠正与 100 条上限在 Service；详情接口在条目不存在（含 id 为
 * {@code null}）时返回 404 与 {@code {"success":false,"message":"提示词不存在"}}；
 * 新增接口只捕获 {@link IllegalArgumentException} 并转成 400，数据库异常等其他失败仍走全局错误处理。
 * 当前四个接口都不加鉴权。</p>
 */
@RestController
@RequestMapping("/api/prompts")
public class PromptLibraryController {

    private final PromptLibraryService service;

    public PromptLibraryController(PromptLibraryService service) {
        this.service = service;
    }

    /**
     * 返回提示词库的筛选元数据。
     *
     * <p>每次调用都会实时执行三条聚合查询（大分类计数、小分类计数、来源计数），没有缓存，
     * 因此库数据变更后刷新页面即可看到新分类与计数。</p>
     *
     * @return 总数、按大分类分组的小分类树和各来源汇总；无数据时各集合为空而不是 {@code null}
     */
    @GetMapping("/meta")
    public PromptMetaResponse meta() {
        return service.meta();
    }

    /**
     * 服务端分页检索提示词，只返回摘要。
     *
     * @param request 由查询串绑定的检索条件：{@code keyword}/{@code group}/{@code category}/
     *                {@code source}/{@code status} 可为空，{@code page} 缺省 1、{@code size} 缺省 48
     * @return 当前页摘要列表，含 {@code total}/{@code page}/{@code size}/{@code entries}；
     *         {@code preview} 是正文前 200 字，完整正文需要再调详情接口
     */
    @GetMapping
    public PromptListResponse list(PromptSearchRequest request) {
        return service.search(request);
    }

    /**
     * 按主键返回单条提示词的完整详情。
     *
     * @param id 路径变量 {@code id}，由 Spring 转换为 {@link Long}；非数字会在进入方法前返回 400
     * @return 命中时 200 加 {@link PromptDetailResponse}（{@code success=true} 与完整正文）；
     *         未命中时 404 加 {@code {"success":false,"message":"提示词不存在"}}
     */
    @GetMapping("/{id}")
    public ResponseEntity<Object> detail(@PathVariable Long id) {
        PromptDetailResponse detail = service.detail(id);
        if (detail == null) {
            Map<String, Object> error = new HashMap<String, Object>();
            error.put("success", false);
            error.put("message", "提示词不存在");
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(error);
        }
        return ResponseEntity.ok(detail);
    }

    /**
     * 手动新增一条提示词。
     *
     * <p>必填与长度校验、大分类推导、{@code manual} 来源的就绪以及 {@code entry_key} 的生成
     * 都在 Service 内完成；本方法只把校验失败（{@link IllegalArgumentException}）翻译成 400，
     * 其余异常保持原样上抛，避免把数据库故障伪装成请求错误。</p>
     *
     * @param request JSON 请求体：{@code title}/{@code category}/{@code prompt} 必填，
     *                {@code tags}/{@code sourceUrl}/{@code license} 可选
     * @return 成功时 200 加 {@code {"success":true,"entry":{...}}}，其中 entry 为落库后重新查询的
     *         完整详情；校验失败时 400 加 {@code {"success":false,"message":"..."}}
     */
    @PostMapping
    public ResponseEntity<Object> create(@RequestBody PromptCreateRequest request) {
        try {
            PromptCreateResponse response = service.create(request);
            return ResponseEntity.ok(response);
        } catch (IllegalArgumentException exception) {
            Map<String, Object> error = new HashMap<String, Object>();
            error.put("success", false);
            error.put("message", exception.getMessage());
            return ResponseEntity.badRequest().body(error);
        }
    }
}