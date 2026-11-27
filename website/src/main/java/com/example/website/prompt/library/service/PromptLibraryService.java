package com.example.website.prompt.library.service;

import com.example.website.prompt.library.dto.PromptCreateRequest;
import com.example.website.prompt.library.dto.PromptCreateResponse;
import com.example.website.prompt.library.dto.PromptDetailResponse;
import com.example.website.prompt.library.dto.PromptListResponse;
import com.example.website.prompt.library.dto.PromptMetaResponse;
import com.example.website.prompt.library.dto.PromptSearchRequest;

/**
 * 提示词库的业务契约，实现见 {@link PromptLibraryServiceImpl}。
 *
 * <p>四个方法分别对应 {@code /api/prompts/meta}、{@code /api/prompts}、{@code /api/prompts/{id}}
 * 与 {@code POST /api/prompts}。约定：查询方法不抛业务异常，未命中用 {@code null} 表示；
 * 写方法用 {@link IllegalArgumentException} 表示可以直接展示给用户的参数错误
 * （字段缺失、超长），由控制器转成 HTTP 400。</p>
 */
public interface PromptLibraryService {

    /**
     * 组装提示词库的筛选元数据。
     *
     * @return 总数、大分类（含小分类与计数）与来源汇总；无数据时返回空集合而不是 {@code null}
     */
    PromptMetaResponse meta();

    /**
     * 按条件分页检索列表摘要。
     *
     * @param request 检索条件与分页参数，调用方需保证非 {@code null}（Spring MVC 会传入绑定后的实例）；
     *                页码与每页条数在这里被纠正到合法范围
     * @return 当页摘要与总数；页码越界时 {@code entries} 为空列表
     */
    PromptListResponse search(PromptSearchRequest request);

    /**
     * 查询单条提示词的完整详情。
     *
     * @param id 条目主键，允许 {@code null}
     * @return 完整详情；{@code id} 为 {@code null} 或记录不存在时返回 {@code null}
     */
    PromptDetailResponse detail(Long id);

    /**
     * 手动新增一条提示词。
     *
     * @param request 新增请求，{@code title}/{@code category}/{@code prompt} 必填且有长度上限
     * @return 含完整详情的新增响应
     * @throws IllegalArgumentException 请求体为空、必填字段缺失或任一字段超长时抛出
     */
    PromptCreateResponse create(PromptCreateRequest request);
}