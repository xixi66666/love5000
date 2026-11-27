package com.example.website.prompt.library.service;

import com.example.website.prompt.library.dao.PromptLibraryDao;
import com.example.website.prompt.library.dto.PromptCreateRequest;
import com.example.website.prompt.library.dto.PromptCreateResponse;
import com.example.website.prompt.library.dto.PromptDetailResponse;
import com.example.website.prompt.library.dto.PromptListResponse;
import com.example.website.prompt.library.dto.PromptMetaResponse;
import com.example.website.prompt.library.dto.PromptSearchRequest;
import com.example.website.prompt.library.model.PromptCategoryStat;
import com.example.website.prompt.library.model.PromptEntry;
import com.example.website.prompt.library.model.PromptGroupStat;
import com.example.website.prompt.library.model.PromptSourceStat;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * 提示词库的业务实现：meta 组装、分页检索、详情映射与手动添加。
 *
 * <p>数据访问全部委托给 {@link PromptLibraryDao}，本类不持有连接、也不声明事务：
 * {@link #create} 的两次写操作（确保 {@code manual} 来源存在、插入条目）是两条各自自动提交的语句，
 * 其中来源写入用 {@code ON DUPLICATE KEY UPDATE} 保证幂等，所以失败重试不会产生重复来源。</p>
 *
 * <p>两个容易忽略的边界：检索关键词在这里完成 LIKE 通配符转义（{@code \}、{@code %}、{@code _}
 * 按字面量匹配），依赖 MySQL 默认的反斜杠转义语义；分页偏移量用 {@code long} 计算，且在偏移量
 * 超过总数时直接返回空页，避免执行无意义的 {@code LIMIT} 或整数溢出。</p>
 *
 * <p>添加时各字段的字符上限见 {@code MAX_*} 常量；未知小分类不报错，而是归入兜底大分类
 * {@code other}，保证新提示词总能出现在分类树里。</p>
 */
@Service
public class PromptLibraryServiceImpl implements PromptLibraryService {

    /** 列表默认每页条数的约定值（48），与 {@link PromptSearchRequest} 的初始值保持一致。 */
    private static final int DEFAULT_SIZE = 48;
    /** 单页条数上限，防止一次拉取过多摘要把响应和内存撑大。 */
    private static final int MAX_SIZE = 100;
    /** 摘要回退长度：SQL 未给出 preview 时取正文前 200 字。 */
    private static final int PREVIEW_CHARS = 200;
    /** 手动添加时标题的字符上限，与 {@code prompt_entry.title} 的列宽对齐。 */
    private static final int MAX_TITLE = 512;
    /** 手动添加时小分类的字符上限，与 {@code prompt_entry.category} 的列宽对齐。 */
    private static final int MAX_CATEGORY = 128;
    /** 手动添加时正文的字符上限，容纳多段生图/生视频提示词。 */
    private static final int MAX_PROMPT = 60000;
    /** 手动添加时标签串的字符上限（统计的是原始入参长度，不是标签个数）。 */
    private static final int MAX_TAGS = 1000;
    /** 手动添加时来源链接的字符上限。 */
    private static final int MAX_SOURCE_URL = 512;
    /** 手动添加时授权的字符上限。 */
    private static final int MAX_LICENSE = 255;
    /** 手动添加来源的固定 id，同时作为 {@code entry_key} 的前缀。 */
    private static final String MANUAL_SOURCE_ID = "manual";
    /** 未知小分类的兜底大分类 slug，对应 {@code prompt_group} 里的“其他”分类。 */
    private static final String DEFAULT_GROUP = "other";

    private final PromptLibraryDao dao;

    public PromptLibraryServiceImpl(PromptLibraryDao dao) {
        this.dao = dao;
    }

    /**
     * 组装筛选面板所需的元数据。
     *
     * <p>先执行三条聚合查询，再把小分类统计按 {@code groupSlug} 分组挂到对应大分类上：
     * 只要 {@code prompt_group} 里有该分类就会出现在结果中，没有小分类时给空列表而不是省略字段。
     * 返回的集合都是新建实例，不复用 DAO 的列表，调用方可以安全修改。</p>
     *
     * @return 总数、大分类树与来源列表；库为空时总数为 0、两个列表为空集合
     */
    @Override
    public PromptMetaResponse meta() {
        List<PromptGroupStat> groupStats = dao.selectGroupCounts();
        List<PromptCategoryStat> categoryStats = dao.selectCategoryCounts();
        List<PromptSourceStat> sourceStats = dao.selectSourceStats();

        Map<String, List<PromptMetaResponse.CategorySummary>> categoriesByGroup = new HashMap<String, List<PromptMetaResponse.CategorySummary>>();
        for (PromptCategoryStat stat : categoryStats) {
            String key = stat.getGroupSlug();
            List<PromptMetaResponse.CategorySummary> list = categoriesByGroup.get(key);
            if (list == null) {
                list = new ArrayList<PromptMetaResponse.CategorySummary>();
                categoriesByGroup.put(key, list);
            }
            list.add(new PromptMetaResponse.CategorySummary(stat.getCategory(), stat.getCount()));
        }

        List<PromptMetaResponse.GroupSummary> groups = new ArrayList<PromptMetaResponse.GroupSummary>();
        for (PromptGroupStat stat : groupStats) {
            PromptMetaResponse.GroupSummary summary = new PromptMetaResponse.GroupSummary();
            summary.setSlug(stat.getSlug());
            summary.setName(stat.getName());
            summary.setCount(stat.getCount());
            List<PromptMetaResponse.CategorySummary> categories = categoriesByGroup.get(stat.getSlug());
            summary.setCategories(categories == null ? new ArrayList<PromptMetaResponse.CategorySummary>() : categories);
            groups.add(summary);
        }

        List<PromptMetaResponse.SourceSummary> sources = new ArrayList<PromptMetaResponse.SourceSummary>();
        for (PromptSourceStat stat : sourceStats) {
            PromptMetaResponse.SourceSummary summary = new PromptMetaResponse.SourceSummary();
            summary.setId(stat.getSourceId());
            summary.setName(stat.getName());
            summary.setStatus(stat.getStatus());
            summary.setCount(stat.getCount());
            summary.setLicense(stat.getLicense());
            summary.setSummary(stat.getSummary());
            sources.add(summary);
        }

        PromptMetaResponse response = new PromptMetaResponse();
        response.setTotal(dao.countAll());
        response.setGroups(groups);
        response.setSources(sources);
        return response;
    }

    /**
     * 按条件分页检索列表摘要。
     *
     * <p>页码小于 1 时归 1，每页条数限制在 1 到 100 之间；五个文本条件都先去空白，空白视为
     * “该条件不过滤”，其中 {@code keyword} 还会做 LIKE 通配符转义。先查总数再判断偏移量是否越界：
     * 越界时直接返回空页，不再发第二条查询。</p>
     *
     * @param request 检索条件与分页参数，不能为 {@code null}（控制器保证传入绑定后的实例）
     * @return 纠正后的 {@code page}/{@code size}、匹配总数与当页摘要；摘要的 {@code preview}
     *         优先使用 SQL 截取结果，为空时退回正文前 200 字
     */
    @Override
    public PromptListResponse search(PromptSearchRequest request) {
        int page = Math.max(1, request.getPage());
        int size = Math.min(MAX_SIZE, Math.max(1, request.getSize()));
        String keyword = escapeLike(trimToNull(request.getKeyword()));
        String group = trimToNull(request.getGroup());
        String category = trimToNull(request.getCategory());
        String source = trimToNull(request.getSource());
        String status = trimToNull(request.getStatus());

        long total = dao.countByFilter(keyword, group, category, source, status);
        // 用 long 计算偏移量，并在页码越界时跳过查询，避免生成无意义的 LIMIT。
        long offset = ((long) page - 1) * size;
        List<PromptEntry> rows = offset < total
                ? dao.searchPage(keyword, group, category, source, status, offset, size)
                : Collections.emptyList();

        List<PromptListResponse.EntrySummary> summaries = new ArrayList<PromptListResponse.EntrySummary>();
        for (PromptEntry row : rows) {
            PromptListResponse.EntrySummary summary = new PromptListResponse.EntrySummary();
            summary.setId(row.getId());
            summary.setTitle(row.getTitle());
            summary.setCategory(row.getCategory());
            summary.setGroupSlug(row.getGroupSlug());
            summary.setGroupName(row.getGroupName());
            summary.setSourceName(row.getSourceName());
            summary.setTags(splitTags(row.getTags()));
            summary.setLicense(row.getLicense());
            summary.setStatus(row.getStatus());
            summary.setPreview(resolvePreview(row));
            summaries.add(summary);
        }

        PromptListResponse response = new PromptListResponse();
        response.setTotal(total);
        response.setPage(page);
        response.setSize(size);
        response.setEntries(summaries);
        return response;
    }

    /**
     * 查询单条提示词的完整详情。
     *
     * @param id 条目主键，允许 {@code null}
     * @return 含完整正文的详情；{@code id} 为 {@code null} 或记录不存在时返回 {@code null}，
     *         由控制器翻译成 HTTP 404
     */
    @Override
    public PromptDetailResponse detail(Long id) {
        if (id == null) {
            return null;
        }
        PromptEntry row = dao.findById(id);
        if (row == null) {
            return null;
        }
        PromptDetailResponse response = new PromptDetailResponse();
        response.setEntry(toEntryDetail(row));
        return response;
    }

    /**
     * 手动添加一条提示词。
     *
     * <p>执行顺序：校验必填与长度 → 规范化标签、来源链接和授权 → 按小分类反查既有大分类
     * （查不到时归 {@code other}）→ 确保 {@code manual} 来源存在 → 以 {@code manual-{uuid}} 作为
     * 入口键插入 → 按新主键重新查询后返回，因此响应里的分类名、来源名都是库中真实值。
     * {@code status} 固定写 {@code imported}，与批量导入的数据保持同一状态口径。</p>
     *
     * @param request 新增请求，不能为 {@code null}
     * @return 含完整详情的新增响应
     * @throws IllegalArgumentException 请求体为空、必填字段去空白后为空，或任一字段超过长度上限时抛出；
     *         异常消息可直接展示给用户
     */
    @Override
    public PromptCreateResponse create(PromptCreateRequest request) {
        if (request == null) {
            throw new IllegalArgumentException("请求体不能为空");
        }
        String title = requireTrimmed(request.getTitle(), "标题不能为空", MAX_TITLE);
        String category = requireTrimmed(request.getCategory(), "小分类不能为空", MAX_CATEGORY);
        String prompt = requireTrimmed(request.getPrompt(), "提示词正文不能为空", MAX_PROMPT);
        String rawTags = trimToNull(request.getTags());
        if (rawTags != null && rawTags.length() > MAX_TAGS) {
            throw new IllegalArgumentException("标签长度不能超过 " + MAX_TAGS + " 个字符");
        }
        String tags = normalizeTags(rawTags);
        String sourceUrl = normalizeOptional(request.getSourceUrl(), "来源链接", MAX_SOURCE_URL);
        String license = normalizeOptional(request.getLicense(), "授权", MAX_LICENSE);

        String groupSlug = dao.findGroupSlugByCategory(category);
        if (groupSlug == null || groupSlug.isEmpty()) {
            groupSlug = DEFAULT_GROUP;
        }
        dao.upsertManualSource();

        PromptEntry entry = new PromptEntry();
        entry.setEntryKey(MANUAL_SOURCE_ID + "-" + UUID.randomUUID());
        entry.setSourceId(MANUAL_SOURCE_ID);
        entry.setTitle(title);
        entry.setCategory(category);
        entry.setGroupSlug(groupSlug);
        entry.setPrompt(prompt);
        entry.setTags(tags);
        entry.setLicense(license);
        entry.setStatus("imported");
        entry.setSourceUrl(sourceUrl);
        dao.insert(entry);

        PromptCreateResponse response = new PromptCreateResponse();
        response.setEntry(toEntryDetail(dao.findById(entry.getId())));
        return response;
    }

    /**
     * 把表行映射成对外详情。
     *
     * @param row 联表查询结果，允许 {@code null}
     * @return 详情对象；{@code row} 为 {@code null} 时返回 {@code null}，便于“未命中”语义向上传递
     */
    private PromptDetailResponse.EntryDetail toEntryDetail(PromptEntry row) {
        if (row == null) {
            return null;
        }
        PromptDetailResponse.EntryDetail detail = new PromptDetailResponse.EntryDetail();
        detail.setId(row.getId());
        detail.setTitle(row.getTitle());
        detail.setCategory(row.getCategory());
        detail.setGroupSlug(row.getGroupSlug());
        detail.setGroupName(row.getGroupName());
        detail.setSourceName(row.getSourceName());
        detail.setSourceUrl(row.getSourceUrl());
        detail.setTags(splitTags(row.getTags()));
        detail.setLicense(row.getLicense());
        detail.setStatus(row.getStatus());
        detail.setPrompt(row.getPrompt());
        return detail;
    }

    /**
     * 校验必填字段：去空白后不得为空，且长度不超过上限。
     *
     * @param value   原始入参，允许 {@code null}
     * @param message 字段缺失时给用户看的前缀文案，例如“标题不能为空”
     * @param max     字符数上限
     * @return 去首尾空白后的值
     * @throws IllegalArgumentException 去空白后为空或超长时抛出，超长消息会拼上具体上限
     */
    private String requireTrimmed(String value, String message, int max) {
        String trimmed = trimToNull(value);
        if (trimmed == null) {
            throw new IllegalArgumentException(message);
        }
        if (trimmed.length() > max) {
            throw new IllegalArgumentException(message + "，长度不能超过 " + max + " 个字符");
        }
        return trimmed;
    }

    /**
     * 规范化可选字段：缺省或纯空白统一成空串，避免库里出现 {@code null} 与空串混用。
     *
     * @param value     原始入参，允许 {@code null}
     * @param fieldName 出错时展示的字段名，例如“来源链接”
     * @param max       字符数上限
     * @return 去空白后的值；缺省时为 {@code ""}
     * @throws IllegalArgumentException 超长时抛出
     */
    private String normalizeOptional(String value, String fieldName, int max) {
        String trimmed = trimToNull(value);
        if (trimmed == null) {
            return "";
        }
        if (trimmed.length() > max) {
            throw new IllegalArgumentException(fieldName + "长度不能超过 " + max + " 个字符");
        }
        return trimmed;
    }

    /**
     * 规范化标签串：按中文或英文逗号拆分，去空白、去重，再用英文逗号重新拼接后落库。
     *
     * <p>统一成英文逗号是为了让输出侧 {@link #splitTags} 和导入数据共用同一种存储格式；
     * 去重保持首次出现顺序（{@link List#contains} 判断），不引入额外集合开销。</p>
     *
     * @param value 原始标签串，允许 {@code null} 或空白
     * @return 规范化后的标签串；无有效标签时返回 {@code ""}
     */
    private String normalizeTags(String value) {
        if (value == null || value.trim().isEmpty()) {
            return "";
        }
        List<String> tags = new ArrayList<String>();
        for (String tag : value.split("[,，]")) {
            String trimmed = tag.trim();
            if (!trimmed.isEmpty() && !tags.contains(trimmed)) {
                tags.add(trimmed);
            }
        }
        return String.join(",", tags);
    }

    /**
     * 把存储侧的标签串拆成对外数组。
     *
     * <p>只按英文逗号拆分：写入时已由 {@link #normalizeTags} 统一过分隔符，历史导入数据同样是英文逗号。
     * 空项会被跳过，因此结果里不会出现空字符串元素。</p>
     *
     * @param tags 数据库中的标签串，允许 {@code null}
     * @return 标签列表；无标签时返回空列表而不是 {@code null}
     */
    private List<String> splitTags(String tags) {
        List<String> result = new ArrayList<String>();
        if (tags == null || tags.trim().isEmpty()) {
            return result;
        }
        for (String tag : tags.split(",")) {
            String trimmed = tag.trim();
            if (!trimmed.isEmpty()) {
                result.add(trimmed);
            }
        }
        return result;
    }

    /**
     * 取列表摘要文本：优先使用 SQL 侧已截断的 {@code preview}，为空时用正文兜底。
     *
     * @param row 列表查询返回的行
     * @return 摘要文本，绝不返回 {@code null}
     */
    private String resolvePreview(PromptEntry row) {
        if (row.getPreview() != null && !row.getPreview().isEmpty()) {
            return row.getPreview();
        }
        return trimPreview(row.getPrompt(), PREVIEW_CHARS);
    }

    /**
     * 正文摘要兜底：把换行归一化为 {@code \n} 后按字符数硬截断。
     *
     * <p>这里不追加省略号，截断标记由前端按布局处理；按 {@code char} 截断，一个表情符号可能落在
     * 两个代理字符之间，摘要文本不做严格字符边界保证。</p>
     *
     * @param prompt 完整正文，允许 {@code null}
     * @param max    最大字符数
     * @return 归一化并截断后的文本；{@code prompt} 为 {@code null} 时返回 {@code ""}
     */
    private String trimPreview(String prompt, int max) {
        if (prompt == null) {
            return "";
        }
        String normalized = prompt.replace("\r\n", "\n");
        if (normalized.length() <= max) {
            return normalized;
        }
        return normalized.substring(0, max);
    }

    /**
     * 去首尾空白，空白串归一化为 {@code null}。
     *
     * <p>检索条件下沉到 DAO 时用 {@code null} 表示“不过滤”，所以空串必须转成 {@code null}
     * 而不是原样传递。</p>
     *
     * @param value 原始文本，允许 {@code null}
     * @return 去空白后的非空文本，或 {@code null}
     */
    private String trimToNull(String value) {
        if (value == null) {
            return null;
        }
        String trimmed = value.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }

    /**
     * 转义 SQL LIKE 的通配符，让用户输入的 {@code %}/{@code _}/{@code \} 按字面量匹配。
     *
     * <p>必须先转义反斜杠再转义其他字符，否则会把新加的转义符再转义一次。转义生效依赖
     * MySQL 默认把反斜杠当作 LIKE 的转义符，SQL 侧没有再显式声明 {@code ESCAPE}。</p>
     *
     * @param value 已去空白的关键词，允许 {@code null}
     * @return 转义后的关键词；入参为 {@code null} 时原样返回
     */
    private String escapeLike(String value) {
        if (value == null) {
            return null;
        }
        return value
                .replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_");
    }
}