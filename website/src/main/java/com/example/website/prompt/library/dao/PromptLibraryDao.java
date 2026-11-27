package com.example.website.prompt.library.dao;

import com.example.website.prompt.library.model.PromptCategoryStat;
import com.example.website.prompt.library.model.PromptEntry;
import com.example.website.prompt.library.model.PromptGroupStat;
import com.example.website.prompt.library.model.PromptSourceStat;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

/**
 * 提示词库的 MyBatis DAO，对应 MySQL {@code xixi} 库的 {@code prompt_entry}、{@code prompt_source}
 * 和 {@code prompt_group} 三张表。
 *
 * <p>SQL 全部集中在 {@code mapper/prompt/PromptLibraryMapper.xml}，本接口不拼语句、不做校验：
 * {@code keyword} 必须由 {@code PromptLibraryServiceImpl} 提前完成 LIKE 通配符转义，
 * 空串或 {@code null} 表示“不按该条件过滤”。查询返回的是联表后的展示模型
 * {@link PromptEntry}（已附带 {@code sourceName}/{@code groupName}），不是纯表实体。</p>
 *
 * <p>写操作只有两条：{@link #insert} 依赖 Mapper 的 {@code useGeneratedKeys} 回填主键，
 * {@link #upsertManualSource} 用 {@code ON DUPLICATE KEY UPDATE} 做幂等写入，重复调用不会产生重复来源。</p>
 */
@Mapper
public interface PromptLibraryDao {

    /**
     * 统计全库条目数，不受任何筛选条件影响。
     *
     * @return {@code prompt_entry} 的总行数，用于 meta 的 {@code total}
     */
    long countAll();

    /**
     * 按筛选条件统计条数，用于分页总数。
     *
     * <p>五个条件都是可选的：{@code null} 或空串在 SQL 动态 where 中被跳过。
     * {@code keyword} 非空时在标题、正文、标签和小分类四列上做 {@code LIKE '%...%'} 匹配，
     * 四个条件之间是 AND 关系。</p>
     *
     * @param keyword  已转义的关键词，可为 {@code null}
     * @param group    大分类 slug，对应 {@code prompt_entry.group_slug}
     * @param category 小分类名称，对应 {@code prompt_entry.category}，精确匹配
     * @param source   来源 id，对应 {@code prompt_entry.source_id}
     * @param status   状态标识，例如 {@code imported}
     * @return 满足条件的总条数；条件全为空时等价于 {@link #countAll()}
     */
    long countByFilter(@Param("keyword") String keyword,
                       @Param("group") String group,
                       @Param("category") String category,
                       @Param("source") String source,
                       @Param("status") String status);

    /**
     * 分页查询列表摘要。
     *
     * <p>结果按 {@code e.id} 升序稳定排序，便于翻页不重不漏；{@code preview} 由 SQL 侧
     * {@code left(coalesce(prompt,''),200)} 生成，因此列表响应不会带完整正文。
     * {@code offset}/{@code size} 直接进入 {@code LIMIT}，由调用方保证非负。</p>
     *
     * @param keyword  已转义的关键词，可为 {@code null}
     * @param group    大分类 slug，可为 {@code null}
     * @param category 小分类名称，可为 {@code null}
     * @param source   来源 id，可为 {@code null}
     * @param status   状态标识，可为 {@code null}
     * @param offset   起始行号（从 0 开始）；超出总数时返回空列表
     * @param size     每页条数，Service 已限制在 1 到 100
     * @return 当前页行；无数据时为空列表
     */
    List<PromptEntry> searchPage(@Param("keyword") String keyword,
                                 @Param("group") String group,
                                 @Param("category") String category,
                                 @Param("source") String source,
                                 @Param("status") String status,
                                 @Param("offset") long offset,
                                 @Param("size") int size);

    /**
     * 按主键查一条完整记录。
     *
     * @param id {@code prompt_entry.id}
     * @return 含完整正文（不截断、不含 preview）的记录；不存在时返回 {@code null}
     */
    PromptEntry findById(@Param("id") Long id);

    /**
     * 插入一条提示词。
     *
     * @param entry 待插入记录，仅使用 {@code entryKey}/{@code sourceId}/{@code title}/{@code category}/
     *              {@code groupSlug}/{@code prompt}/{@code tags}/{@code license}/{@code status}/
     *              {@code sourceUrl} 这些列；成功后 {@code id} 被回填
     * @return 受影响行数，正常为 1
     */
    int insert(PromptEntry entry);

    /**
     * 按小分类反查其所属大分类。
     *
     * <p>取该小分类下出现次数最多的 {@code group_slug}（{@code order by count(*) desc limit 1}），
     * 供手动添加时推导归属；同一小分类被历史数据分到多个大分类时取占比最高的那个。</p>
     *
     * @param category 小分类名称
     * @return 大分类 slug；该小分类还没有任何记录时返回 {@code null}
     */
    String findGroupSlugByCategory(@Param("category") String category);

    /**
     * 确保“手动添加”来源存在，并把它的名称、授权和摘要刷新为固定文案。
     *
     * <p>MySQL 的 {@code INSERT ... ON DUPLICATE KEY UPDATE}，以 {@code source_id='manual'} 为冲突键，
     * 因此可重复调用而不会写出重复来源。</p>
     *
     * @return 受影响行数；MySQL 语义下重复命中可能返回 0
     */
    int upsertManualSource();

    /**
     * 统计每个大分类的条目数，用于 meta 的大分类列表。
     *
     * <p>以 {@code prompt_group} 为主表左连条目，按 {@code sort_order} 排序：即使某个大分类下
     * 暂无视提示词也会返回，计数为 0，保证前端分类树不因空分类而缺项。</p>
     *
     * @return 大分类统计行，按预置顺序排列
     */
    List<PromptGroupStat> selectGroupCounts();

    /**
     * 统计“大分类 + 小分类”组合的条目数，用于在 meta 中挂载二级分类。
     *
     * <p>与 {@link #selectGroupCounts()} 不同，这里从 {@code prompt_entry} 聚合，只统计实际存在
     * 提示词的小分类，并按计数降序，让常用小分类排在前面。</p>
     *
     * @return 小分类统计行，含所属大分类 slug
     */
    List<PromptCategoryStat> selectCategoryCounts();

    /**
     * 统计每个来源的条目数与展示字段，用于 meta 的来源列表。
     *
     * <p>以 {@code prompt_source} 为主表左连条目，按来源自增 id 排序；没有条目的来源仍会返回，
     * 计数为 0。</p>
     *
     * @return 来源统计行
     */
    List<PromptSourceStat> selectSourceStats();
}