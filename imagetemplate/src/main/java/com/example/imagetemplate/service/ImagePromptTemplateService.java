package com.example.imagetemplate.service;

import com.example.imagetemplate.dto.ImageTemplateMetaResponse;
import com.example.imagetemplate.dto.ImageTemplatePageResponse;
import com.example.imagetemplate.dto.ImageTemplateQuery;
import com.example.imagetemplate.dto.ImageTemplateSummaryResponse;
import com.example.imagetemplate.dto.PromptRenderRequest;
import com.example.imagetemplate.dto.TemplateCategoryResponse;
import com.example.imagetemplate.dto.TemplateFunctionCategoryResponse;
import com.example.imagetemplate.dto.TemplateFunctionSceneResponse;
import com.example.imagetemplate.dto.TemplateSourceResponse;
import com.example.imagetemplate.model.ImagePromptTemplate;
import com.example.imagetemplate.model.LibraryAggregationStatus;
import com.example.imagetemplate.model.PromptLibraryLoadResult;
import com.example.imagetemplate.model.PromptLibrarySource;
import com.example.imagetemplate.model.TemplateFunctionClassification;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * 图片提示词模板聚合服务。
 *
 * <p>启动时把两份 classpath 数据合成一个只读快照：47 条精选模板
 * （{@code templates/image-prompt-templates.json}）加 4409 条 Prompt Console 大库
 * （构建期由 website 唯一源复制而来）。构造期一次性完成来源标记、功能分类、
 * ID 索引、检索索引、来源/分类/功能树计数，之后所有读请求只做过滤与分页，
 * 不再触碰磁盘、不再重算分类，因此可以并发调用而无需加锁。</p>
 *
 * <p>降级策略：任一数据源缺失、条数不符或解析失败都不会让服务启动失败，
 * 而是尽可能多地聚合可用条目，并在 {@link LibraryAggregationStatus} 中输出
 * 预期数量、实际数量与中文原因；{@code status} 变成 {@code DEGRADED}
 * 后列表页与 {@code /meta} 都会带上同样的告警，避免把 47 条精选误当成完整数据。</p>
 *
 * <p>本类与 {@link PromptLibraryLoader}（容错加载）、{@link ImagePromptTemplateAdapter}
 * （大库条目映射）、{@link TemplateFunctionClassifier}（功能树判定）、
 * {@link TemplateSearchIndex}（检索字段预计算）协作，不自带任何缓存刷新入口。</p>
 */
@Service
public class ImagePromptTemplateService {

    /** 精选模板预期条数；与实际不符时服务仍可启动，但聚合状态降为 {@code DEGRADED}。 */
    private static final int EXPECTED_CURATED_COUNT = 47;

    /** Prompt Console 大库预期有效条数；与 {@link PromptLibraryLoader} 的原始条数校验互为补充。 */
    private static final int EXPECTED_LIBRARY_COUNT = 4409;

    /** 聚合后的完整模板列表（精选在前、大库在后），构造后不可变，作为所有查询的稳定快照。 */
    private final List<ImagePromptTemplate> templates;

    /** ID 到模板的索引；重复 ID 在构造期直接抛错，避免详情接口命中不确定的对象。 */
    private final Map<String, ImagePromptTemplate> templatesById;

    /** ID 到预计算检索字段的索引，使列表过滤不必每次请求都归一化字符串。 */
    private final Map<String, TemplateSearchIndex> searchIndexById;

    /** 聚合健康度（含预期/实际数量与降级原因），随列表与 meta 接口一起返回。 */
    private final LibraryAggregationStatus aggregationStatus;

    /** 来源列表，精选来源固定排第一位，其余按大库来源声明顺序。 */
    private final List<TemplateSourceResponse> sources;

    /** 15 个一级功能及其二级场景的计数树，顺序即前端导航顺序。 */
    private final List<TemplateFunctionCategoryResponse> functionCategories;

    /** 原始分类（{@code categorySlug}）计数，供旧的分类筛选使用。 */
    private final List<TemplateCategoryResponse> categories;

    /** 图片相关模板总数，供页面“仅图片”开关展示。 */
    private final int imageRelatedCount;

    /** 精选模板加载失败时的原因；仅在构造期写入，随后由 {@link #buildStatus} 汇总进降级消息。 */
    private String curatedLoadMessage = "";

    /**
     * 构造并冻结聚合快照。
     *
     * <p>加载顺序固定：精选模板 → 大库 → 合并 → 逐条功能分类 → 建索引与统计。
     * 精选模板按原文件顺序整体排在前面，大库条目保持加载顺序，
     * 前端“默认第一页”因此稳定可复现。</p>
     *
     * @param objectMapper       读取精选模板 JSON 的映射器
     * @param promptLibraryLoader 大库容错加载器，失败时返回空条目而非抛异常
     * @param adapter            大库条目到模板模型的适配器
     * @param functionClassifier 功能树判定器，只读元数据，不解析完整 Prompt
     * @throws IllegalStateException 聚合结果出现重复模板 ID 时抛出，暴露数据源冲突
     */
    public ImagePromptTemplateService(ObjectMapper objectMapper,
                                      PromptLibraryLoader promptLibraryLoader,
                                      ImagePromptTemplateAdapter adapter,
                                      TemplateFunctionClassifier functionClassifier) {
        List<ImagePromptTemplate> curated = loadCuratedTemplates(objectMapper);
        decorateCurated(curated);

        PromptLibraryLoadResult libraryResult = promptLibraryLoader.loadDefault();
        List<ImagePromptTemplate> imported = adapter.adapt(libraryResult.getEntries());

        List<ImagePromptTemplate> aggregated = new ArrayList<ImagePromptTemplate>();
        aggregated.addAll(curated);
        aggregated.addAll(imported);
        decorateFunctionalClassifications(aggregated, functionClassifier);
        this.templates = Collections.unmodifiableList(aggregated);
        this.templatesById = Collections.unmodifiableMap(indexById(aggregated));
        this.searchIndexById = Collections.unmodifiableMap(indexForSearch(aggregated));
        this.aggregationStatus =
                buildStatus(curated.size(), imported.size(), libraryResult);
        this.sources = Collections.unmodifiableList(
                buildSources(libraryResult.getSources(), aggregated));
        this.functionCategories = Collections.unmodifiableList(
                buildFunctionCategories(functionClassifier, aggregated));
        this.categories = Collections.unmodifiableList(buildCategories(aggregated));
        this.imageRelatedCount = countImageRelated(aggregated);
    }

    /**
     * 按条件过滤并分页返回摘要列表。
     *
     * <p>不带任何过滤条件且未开启“仅图片”时直接复用全量列表，不复制集合；
     * 一旦有索引类过滤（来源、原始分类、一级功能、二级场景、关键词任一命中）
     * 就退化为一次线性扫描，逐条复用预计算好的 {@link TemplateSearchIndex}。
     * {@code "all"} 与空白值都视为“不筛选”。</p>
     *
     * <p>分页先算 64 位的起始下标再截断，避免大页码时 {@code (page-1)*size} 溢出成负数；
     * 起始下标超过总数时返回空 {@code templates} 且 {@code hasMore=false}，不抛异常。
     * 列表只填摘要字段，完整 {@code promptTemplate} 与 {@code jsonTemplate} 必须走详情接口。</p>
     *
     * @param query 查询条件，{@code null} 时按默认分页（第 1 页、每页 48 条）处理
     * @return 当前页摘要、过滤后总数、分页边界与聚合状态
     * @throws ImageTemplateQueryValidationException {@code page < 1} 或 {@code size} 不在 1 到 100 之间
     */
    public ImageTemplatePageResponse search(ImageTemplateQuery query) {
        ImageTemplateQuery actual = query == null ? new ImageTemplateQuery() : query;
        validate(actual);

        String normalizedSource = normalize(actual.getSource());
        String normalizedCategory = normalize(actual.getCategory());
        String normalizedFunctionCategory =
                normalize(actual.getFunctionCategory());
        String normalizedFunctionScene = normalize(actual.getFunctionScene());
        String normalizedKeyword = normalize(actual.getKeyword());
        boolean sourceFiltered = hasText(normalizedSource) && !"all".equals(normalizedSource);
        boolean categoryFiltered = hasText(normalizedCategory) && !"all".equals(normalizedCategory);
        boolean functionCategoryFiltered =
                hasText(normalizedFunctionCategory) && !"all".equals(normalizedFunctionCategory);
        boolean functionSceneFiltered =
                hasText(normalizedFunctionScene) && !"all".equals(normalizedFunctionScene);
        boolean keywordFiltered = hasText(normalizedKeyword);
        boolean indexedFilter = sourceFiltered || categoryFiltered
                || functionCategoryFiltered || functionSceneFiltered || keywordFiltered;
        List<ImagePromptTemplate> filtered;
        if (!indexedFilter && !actual.isImageOnly()) {
            filtered = templates;
        } else {
            filtered = new ArrayList<ImagePromptTemplate>();
            for (ImagePromptTemplate template : templates) {
                if (actual.isImageOnly() && !template.isImageRelated()) {
                    continue;
                }
                if (indexedFilter) {
                    TemplateSearchIndex index = searchIndexById.get(template.getId());
                    if ((sourceFiltered && !index.matchesSource(normalizedSource))
                            || (categoryFiltered && !index.matchesCategory(normalizedCategory))
                            || (functionCategoryFiltered
                                && !index.matchesFunctionCategory(normalizedFunctionCategory))
                            || (functionSceneFiltered
                                && !index.matchesFunctionScene(normalizedFunctionScene))
                            || (keywordFiltered
                                && !index.matchesKeyword(normalizedKeyword))) {
                        continue;
                    }
                }
                filtered.add(template);
            }
        }

        long fromLong = ((long) actual.getPage() - 1L) * actual.getSize();
        int fromIndex = fromLong >= filtered.size() ? filtered.size() : (int) fromLong;
        int toIndex = Math.min(filtered.size(), fromIndex + actual.getSize());
        List<ImageTemplateSummaryResponse> summaries =
                new ArrayList<ImageTemplateSummaryResponse>();
        for (ImagePromptTemplate template : filtered.subList(fromIndex, toIndex)) {
            summaries.add(ImageTemplateSummaryResponse.from(template));
        }

        ImageTemplatePageResponse response = new ImageTemplatePageResponse();
        response.setTotal(filtered.size());
        response.setPage(actual.getPage());
        response.setSize(actual.getSize());
        response.setHasMore(toIndex < filtered.size());
        response.setLibraryStatus(aggregationStatus.getStatus());
        response.setMessage(aggregationStatus.getMessage());
        response.setTemplates(summaries);
        return response;
    }

    /**
     * 组装聚合元数据。
     *
     * <p>返回总量、精选与大库的实际条数、图片相关数量、{@code READY}/{@code DEGRADED}
     * 状态（含预期数量、实际数量与中文原因）、来源、原始分类和两级功能树。
     * 列表结构都返回副本，调用方修改响应对象不会污染构造期冻结的内部数据。</p>
     *
     * @return 元数据响应，{@code status} 中携带降级诊断信息
     */
    public ImageTemplateMetaResponse getMeta() {
        ImageTemplateMetaResponse response = new ImageTemplateMetaResponse();
        response.setTotal(templates.size());
        response.setCuratedCount(aggregationStatus.getLoadedCuratedCount());
        response.setLibraryCount(aggregationStatus.getLoadedLibraryCount());
        response.setImageRelatedCount(imageRelatedCount);
        response.setStatus(aggregationStatus);
        response.setSources(new ArrayList<TemplateSourceResponse>(sources));
        response.setCategories(copyCategories(categories));
        response.setFunctionCategories(
                new ArrayList<TemplateFunctionCategoryResponse>(functionCategories));
        return response;
    }

    /**
     * 兼容旧接口的完整列表查询。
     *
     * <p>只支持原始分类与关键词两个条件，不分页且返回聚合列表中的模板对象本身
     * （含完整 Prompt），仅供内部或历史调用方使用；面向页面的分页摘要应走
     * {@link #search(ImageTemplateQuery)}。{@code "all"} 与空白值视为不筛选。</p>
     *
     * @param category 原始分类 slug 或中文名，可为 {@code null}
     * @param keyword  关键词，可为 {@code null}
     * @return 命中的模板引用列表，未筛选时为全量列表
     */
    public List<ImagePromptTemplate> listTemplates(String category, String keyword) {
        String normalizedCategory = normalize(category);
        String normalizedKeyword = normalize(keyword);
        boolean categoryFiltered =
                hasText(normalizedCategory) && !"all".equals(normalizedCategory);
        boolean keywordFiltered = hasText(normalizedKeyword);
        List<ImagePromptTemplate> result = new ArrayList<ImagePromptTemplate>();
        for (ImagePromptTemplate template : templates) {
            if (categoryFiltered || keywordFiltered) {
                TemplateSearchIndex index = searchIndexById.get(template.getId());
                if ((categoryFiltered && !index.matchesCategory(normalizedCategory))
                        || (keywordFiltered && !index.matchesKeyword(normalizedKeyword))) {
                    continue;
                }
            }
            result.add(template);
        }
        return result;
    }

    /**
     * 返回原始分类计数：按 {@code categorySlug} 分组，顺序为首次出现顺序。
     * 每次调用都新建列表对象，调用方可以直接修改。
     *
     * @return 分类响应列表，不会为 {@code null}
     */
    public List<TemplateCategoryResponse> listCategories() {
        return copyCategories(categories);
    }

    /**
     * 按 ID 查找模板。
     *
     * @param id 模板 ID，精选与 {@code library-} 前缀的大库 ID 都在同一索引中
     * @return 聚合列表中的模板对象（含完整 Prompt 与结构化模板）
     * @throws ImagePromptTemplateNotFoundException 未命中时抛出，由 Controller 转为 404
     */
    public ImagePromptTemplate findById(String id) {
        ImagePromptTemplate template = templatesById.get(id);
        if (template == null) {
            throw new ImagePromptTemplateNotFoundException(id);
        }
        return template;
    }

    /**
     * 把模板渲染成可直接提交给图片生成接口的提示词。
     *
     * <p>按 {@code templateKind} 分两条路径：</p>
     * <ul>
     *   <li>{@code DIRECT}（含精选中的 {@code direct-prompt} 与大库全部条目）：
     *       以 {@code promptTemplate} 原文为底，非空用户变量以“用户变量”段落追加，
     *       再追加“用户补充要求”，不做占位符替换。</li>
     *   <li>其余按结构化模板处理：先用变量覆盖同名 key 得到解析后的 JSON 树，
     *       再渲染成缩进列表文本，并与标题、常规模板和固定的输出约束拼成完整任务描述。</li>
     * </ul>
     *
     * <p>{@code request} 为 {@code null} 时按“无变量、无补充要求”渲染，不报错。</p>
     *
     * @param id      模板 ID
     * @param request 渲染请求，含变量表与补充要求，可为 {@code null}
     * @return 最终提示词文本
     * @throws ImagePromptTemplateNotFoundException 模板 ID 不存在
     */
    public String renderPrompt(String id, PromptRenderRequest request) {
        ImagePromptTemplate template = findById(id);
        Map<String, Object> variables = request == null ? null : request.getVariables();
        String extraInstruction = request == null ? null : request.getExtraInstruction();
        if ("DIRECT".equals(template.getTemplateKind())) {
            StringBuilder direct = new StringBuilder(template.getPromptTemplate().trim());
            if (variables != null && !variables.isEmpty()) {
                direct.append("\n\n用户变量：\n");
                appendMap(direct, variables, 0);
            }
            if (hasText(extraInstruction)) {
                direct.append("\n\n用户补充要求：").append(extraInstruction.trim());
            }
            return direct.toString();
        }

        Map<String, Object> resolvedTemplate =
                resolveTemplate(template.getJsonTemplate(), variables);
        StringBuilder prompt = new StringBuilder();
        prompt.append("图像生成任务：").append(template.getTitle()).append("\n\n");
        prompt.append("常规模板：").append(template.getPromptTemplate()).append("\n\n");
        prompt.append("请将下面的结构化 JSON 模板转化为一个自然、明确、可直接传入图像生成接口 prompt 字段的高质量提示词：\n");
        appendMap(prompt, resolvedTemplate, 0);
        if (hasText(extraInstruction)) {
            prompt.append("\n用户补充要求：").append(extraInstruction.trim()).append("\n");
        }
        prompt.append("\n输出要求：保持主体、风格、构图、材质、文字和限制条件一致；如模板包含精确文字，必须逐字准确；不要在图像中加入模板之外的水印、签名或额外文字。");
        return prompt.toString();
    }

    /**
     * 从 classpath 读取精选模板 JSON。
     *
     * <p>解析失败不抛异常：把原因记入 {@code curatedLoadMessage} 并返回空列表，
     * 让服务带着 {@code DEGRADED} 状态启动，页面仍可浏览大库条目并显示错误原因。</p>
     *
     * @param objectMapper Jackson 映射器
     * @return 精选模板列表；失败时为空列表而非 {@code null}
     */
    private List<ImagePromptTemplate> loadCuratedTemplates(ObjectMapper objectMapper) {
        try {
            return objectMapper.readValue(
                    new ClassPathResource("templates/image-prompt-templates.json").getInputStream(),
                    new TypeReference<List<ImagePromptTemplate>>() {
                    });
        } catch (IOException | RuntimeException exception) {
            curatedLoadMessage = "精选模板加载失败：" + exception.getMessage();
            return new ArrayList<ImagePromptTemplate>();
        }
    }

    /**
     * 为精选模板补齐精选库特有的字段。
     *
     * <p>精选来源统一标记为 {@code curated}/“精选模板”；分类 slug 为 {@code direct-prompt}
     * 的视为直接提示词（{@code DIRECT}），其余按结构化模板（{@code STRUCTURED}）渲染；
     * 精选一律视为图片相关，因为整个精选库就是为图片生成整理的。</p>
     *
     * @param curated 已加载的精选模板（原地修改）
     */
    private void decorateCurated(List<ImagePromptTemplate> curated) {
        for (ImagePromptTemplate template : curated) {
            template.setSourceId("curated");
            template.setSourceName("精选模板");
            template.setTemplateKind("direct-prompt".equals(template.getCategorySlug())
                    ? "DIRECT"
                    : "STRUCTURED");
            template.setImageRelated(true);
            template.setCurated(true);
        }
    }

    /**
     * 为所有模板（精选与大库）写入一级功能与二级场景。
     *
     * <p>整批只调用一次，结果写回模板字段，后续筛选和计数都读这些字段，
     * 不会在请求期重复分类。分类依据是 ID、标题、分类、标签与来源，
     * 不读取完整 Prompt 正文。</p>
     *
     * @param values            合并后的模板列表（原地修改）
     * @param functionClassifier 功能树判定器
     */
    private void decorateFunctionalClassifications(
            List<ImagePromptTemplate> values,
            TemplateFunctionClassifier functionClassifier) {
        for (ImagePromptTemplate template : values) {
            TemplateFunctionClassification classification =
                    functionClassifier.classify(template);
            template.setFunctionCategory(classification.getCategoryName());
            template.setFunctionCategorySlug(classification.getCategorySlug());
            template.setFunctionScene(classification.getSceneName());
            template.setFunctionSceneSlug(classification.getSceneSlug());
        }
    }

    /**
     * 按分类器目录装配两级功能树。
     *
     * <p>一级与二级节点都以分类器声明的目录为准，即使某场景当前没有任何模板也会保留
     * （计数为 0），从而保证前端导航结构稳定、一级计数之和等于实际模板总数。
     * 计数取自已经写入模板的功能字段，不再重新分类。</p>
     *
     * @param functionClassifier 提供目录顺序与节点名称
     * @param values            已完成功能分类的模板
     * @return 15 个一级功能（含各自二级场景计数）的有序列表
     */
    private List<TemplateFunctionCategoryResponse> buildFunctionCategories(
            TemplateFunctionClassifier functionClassifier,
            List<ImagePromptTemplate> values) {
        Map<String, Integer> categoryCounts = new LinkedHashMap<String, Integer>();
        Map<String, Integer> sceneCounts = new LinkedHashMap<String, Integer>();
        for (ImagePromptTemplate template : values) {
            increment(categoryCounts, template.getFunctionCategorySlug());
            increment(sceneCounts, template.getFunctionCategorySlug()
                    + "/" + template.getFunctionSceneSlug());
        }

        List<TemplateFunctionCategoryResponse> result =
                new ArrayList<TemplateFunctionCategoryResponse>();
        for (TemplateFunctionClassifier.CategoryDefinition category
                : functionClassifier.getCatalog()) {
            List<TemplateFunctionSceneResponse> scenes =
                    new ArrayList<TemplateFunctionSceneResponse>();
            for (TemplateFunctionClassifier.SceneDefinition scene
                    : category.getScenes()) {
                scenes.add(new TemplateFunctionSceneResponse(
                        scene.getName(),
                        scene.getSlug(),
                        count(sceneCounts, category.getSlug() + "/" + scene.getSlug())));
            }
            result.add(new TemplateFunctionCategoryResponse(
                    category.getName(),
                    category.getSlug(),
                    count(categoryCounts, category.getSlug()),
                    scenes));
        }
        return result;
    }

    /** 计数加一：键不存在时从 1 开始，用于功能树与来源统计的一次性累积。 */
    private void increment(Map<String, Integer> counts, String key) {
        counts.put(key, counts.containsKey(key) ? counts.get(key) + 1 : 1);
    }

    /**
     * 构建 ID 索引并校验唯一性。
     *
     * <p>聚合列表里出现重复 ID 说明精选库与大库冲突，或大库指纹生成失效；
     * 这类问题必须在启动期暴露，否则详情接口会随机命中其中一条。</p>
     *
     * @param values 聚合后的模板列表
     * @return 保持插入顺序的 ID 索引
     * @throws IllegalStateException 存在重复 ID
     */
    private Map<String, ImagePromptTemplate> indexById(List<ImagePromptTemplate> values) {
        Map<String, ImagePromptTemplate> indexed =
                new LinkedHashMap<String, ImagePromptTemplate>();
        for (ImagePromptTemplate template : values) {
            if (indexed.containsKey(template.getId())) {
                throw new IllegalStateException("Duplicate aggregate template id: "
                        + template.getId());
            }
            indexed.put(template.getId(), template);
        }
        return indexed;
    }

    /**
     * 为每条模板预计算检索字段。
     *
     * <p>归一化与字符串拼接只在这里做一次，列表过滤时只做 contains/equals，
     * 避免每次请求对 4456 条模板重复小写化。</p>
     *
     * @param values 聚合后的模板列表
     * @return ID 到检索索引的映射
     */
    private Map<String, TemplateSearchIndex> indexForSearch(
            List<ImagePromptTemplate> values) {
        Map<String, TemplateSearchIndex> indexed =
                new LinkedHashMap<String, TemplateSearchIndex>();
        for (ImagePromptTemplate template : values) {
            indexed.put(template.getId(), new TemplateSearchIndex(template));
        }
        return indexed;
    }

    /**
     * 按 {@code categorySlug} 汇总原始分类计数。
     *
     * <p>首次遇到某 slug 时用该条目的中文分类名建节点，因此同名 slug 的不同中文写法
     * 以先出现者为准；结果顺序即首次出现顺序，不额外排序。</p>
     *
     * @param values 聚合后的模板列表
     * @return 分类响应列表
     */
    private List<TemplateCategoryResponse> buildCategories(
            List<ImagePromptTemplate> values) {
        Map<String, TemplateCategoryResponse> categories =
                new LinkedHashMap<String, TemplateCategoryResponse>();
        for (ImagePromptTemplate template : values) {
            String slug = template.getCategorySlug();
            TemplateCategoryResponse category = categories.get(slug);
            if (category == null) {
                category = new TemplateCategoryResponse(
                        template.getCategory(), slug, 0);
                categories.put(slug, category);
            }
            category.setCount(category.getCount() + 1);
        }
        return new ArrayList<TemplateCategoryResponse>(categories.values());
    }

    /**
     * 复制分类列表。
     *
     * <p>返回的元素都是新建对象：{@code TemplateCategoryResponse} 的 {@code count} 在聚合期
     * 会被累加，如果直接把内部对象交出去，调用方一改就会污染同一 JVM 内的其他响应。</p>
     *
     * @param values 内部不可变分类列表
     * @return 元素为新建对象的副本列表
     */
    private List<TemplateCategoryResponse> copyCategories(
            List<TemplateCategoryResponse> values) {
        List<TemplateCategoryResponse> copies =
                new ArrayList<TemplateCategoryResponse>(values.size());
        for (TemplateCategoryResponse value : values) {
            copies.add(new TemplateCategoryResponse(
                    value.getName(), value.getSlug(), value.getCount()));
        }
        return copies;
    }

    /**
     * 汇总聚合健康度。
     *
     * <p>只要产生任何一条诊断消息（精选加载失败、精选条数不符、大库消息、大库有效条数不符），
     * 状态即为 {@code DEGRADED}，否则为 {@code READY}；消息用中文分号拼接，
     * 同时带出预期数量与实际数量，便于页面直接展示差异。</p>
     *
     * @param curatedCount  实际加载的精选条数
     * @param libraryCount  实际可用的大库条数
     * @param libraryResult 大库加载结果，提供解析/校验消息
     * @return 聚合状态对象
     */
    private LibraryAggregationStatus buildStatus(int curatedCount,
                                                 int libraryCount,
                                                 PromptLibraryLoadResult libraryResult) {
        List<String> messages = new ArrayList<String>();
        if (hasText(curatedLoadMessage)) {
            messages.add(curatedLoadMessage);
        }
        if (curatedCount != EXPECTED_CURATED_COUNT) {
            messages.add("精选模板预期 " + EXPECTED_CURATED_COUNT + "，实际 " + curatedCount);
        }
        if (hasText(libraryResult.getMessage())) {
            messages.add(libraryResult.getMessage());
        }
        if (libraryCount != EXPECTED_LIBRARY_COUNT) {
            messages.add("大库有效条目预期 " + EXPECTED_LIBRARY_COUNT
                    + "，实际 " + libraryCount);
        }

        LibraryAggregationStatus status = new LibraryAggregationStatus();
        status.setExpectedCuratedCount(EXPECTED_CURATED_COUNT);
        status.setLoadedCuratedCount(curatedCount);
        status.setExpectedLibraryCount(EXPECTED_LIBRARY_COUNT);
        status.setLoadedLibraryCount(libraryCount);
        status.setTotal(curatedCount + libraryCount);
        status.setMessage(join(messages));
        status.setStatus(messages.isEmpty() ? "READY" : "DEGRADED");
        return status;
    }

    /**
     * 组装来源列表。
     *
     * <p>精选来源固定排在第一位，其余来源按大库声明的顺序追加；计数来自聚合结果而非
     * 大库文件，所以降级加载时显示的仍是真实已加载条数。大库未声明的来源不会出现在
     * 来源列表里，但其条目仍计入总数，这就出现了“各来源计数之和小于总数”的情况。</p>
     *
     * @param librarySources 大库声明的来源元数据，可为 {@code null}
     * @param aggregated     聚合后的模板列表
     * @return 有序来源列表
     */
    private List<TemplateSourceResponse> buildSources(
            List<PromptLibrarySource> librarySources,
            List<ImagePromptTemplate> aggregated) {
        Map<String, Integer> counts = new LinkedHashMap<String, Integer>();
        for (ImagePromptTemplate template : aggregated) {
            String id = template.getSourceId();
            counts.put(id, counts.containsKey(id) ? counts.get(id) + 1 : 1);
        }

        List<TemplateSourceResponse> result = new ArrayList<TemplateSourceResponse>();
        result.add(new TemplateSourceResponse(
                "curated", "精选模板", "", count(counts, "curated")));
        if (librarySources != null) {
            for (PromptLibrarySource source : librarySources) {
                result.add(new TemplateSourceResponse(
                        source.getId(),
                        source.getName(),
                        source.getUrl(),
                        count(counts, source.getId())));
            }
        }
        return result;
    }

    /**
     * 读取计数，缺省为 0。
     *
     * <p>大库声明的来源可能在降级加载时没有任何条目，用 0 而不是 {@code null}
     * 保证响应的 {@code count} 字段始终是数字。</p>
     *
     * @param counts   计数表
     * @param sourceId 来源 ID
     * @return 该来源的模板数
     */
    private int count(Map<String, Integer> counts, String sourceId) {
        Integer count = counts.get(sourceId);
        return count == null ? 0 : count;
    }

    /**
     * 统计图片相关模板数量。
     *
     * @param values 聚合后的模板列表
     * @return 标记为图片相关的模板数
     */
    private int countImageRelated(List<ImagePromptTemplate> values) {
        int count = 0;
        for (ImagePromptTemplate template : values) {
            if (template.isImageRelated()) {
                count++;
            }
        }
        return count;
    }

    /**
     * 校验分页参数。
     *
     * <p>阈值与前端“加载更多”约定一致：{@code page} 至少为 1，{@code size} 在 1 到 100 之间
     * （默认 48）。越界时抛出异常由 Controller 转成 HTTP 400，不会退化成静默截断，
     * 避免前端以为拿到了完整数据。</p>
     *
     * @param query 已归一化（非 {@code null}）的查询条件
     * @throws ImageTemplateQueryValidationException 分页参数越界
     */
    private void validate(ImageTemplateQuery query) {
        if (query.getPage() < 1) {
            throw new ImageTemplateQueryValidationException("page 必须大于等于 1");
        }
        if (query.getSize() < 1 || query.getSize() > 100) {
            throw new ImageTemplateQueryValidationException("size 必须在 1 到 100 之间");
        }
    }

    /**
     * 用用户变量覆盖结构化模板的同名键。
     *
     * <p>只处理最外层键：命中变量表时用变量值替换默认值，再交给
     * {@link #resolveValue} 处理嵌套结构；未命中的键保留模板默认值。</p>
     *
     * @param jsonTemplate 模板自带的结构化 JSON，可为 {@code null}
     * @param variables    用户变量表，可为 {@code null}
     * @return 解析后的新 Map，保持原键顺序；入参为 {@code null} 时返回空 Map
     */
    private Map<String, Object> resolveTemplate(Map<String, Object> jsonTemplate,
                                                Map<String, Object> variables) {
        Map<String, Object> resolved = new LinkedHashMap<String, Object>();
        if (jsonTemplate == null) {
            return resolved;
        }
        for (Map.Entry<String, Object> entry : jsonTemplate.entrySet()) {
            Object value = entry.getValue();
            if (variables != null && variables.containsKey(entry.getKey())) {
                value = variables.get(entry.getKey());
            }
            resolved.put(entry.getKey(), resolveValue(value, variables));
        }
        return resolved;
    }

    /**
     * 递归解析嵌套 Map 与 List 中的变量。
     *
     * <p>变量按 key 名全局匹配，不区分层级命名空间：同一 key 在多层出现都会被同一变量覆盖，
     * 这是模板字段名需要保持稳定的原因。返回值为深拷贝后的新结构，标量原样透传。</p>
     *
     * @param value     模板中的默认值，可以是 Map、List 或标量
     * @param variables 用户变量表，可为 {@code null}
     * @return 替换后的值
     */
    @SuppressWarnings("unchecked")
    private Object resolveValue(Object value, Map<String, Object> variables) {
        if (value instanceof Map) {
            Map<String, Object> valueMap = (Map<String, Object>) value;
            Map<String, Object> resolved = new LinkedHashMap<String, Object>();
            for (Map.Entry<String, Object> entry : valueMap.entrySet()) {
                Object nestedValue = entry.getValue();
                if (variables != null && variables.containsKey(entry.getKey())) {
                    nestedValue = variables.get(entry.getKey());
                }
                resolved.put(entry.getKey(), resolveValue(nestedValue, variables));
            }
            return resolved;
        }
        if (value instanceof List) {
            List<Object> resolved = new ArrayList<Object>();
            for (Object item : (List<Object>) value) {
                resolved.add(resolveValue(item, variables));
            }
            return resolved;
        }
        return value;
    }

    /**
     * 把一个值渲染成提示词片段。
     *
     * <p>Map 递归成带缩进的键值列表；List 每个元素独占一行并加 {@code - } 前缀；
     * 标量直接输出，{@code null} 输出空串。缩进用两个空格递增，
     * 让最终 prompt 在纯文本里仍然保持结构可读。</p>
     *
     * @param prompt 输出缓冲
     * @param value  待渲染值
     * @param indent 当前缩进层级
     */
    @SuppressWarnings("unchecked")
    private void appendValue(StringBuilder prompt, Object value, int indent) {
        if (value instanceof Map) {
            prompt.append("\n");
            appendMap(prompt, (Map<String, Object>) value, indent + 1);
            return;
        }
        if (value instanceof List) {
            List<Object> values = (List<Object>) value;
            for (Object item : values) {
                prompt.append("\n").append(indent(indent + 1)).append("- ");
                appendValue(prompt, item, indent + 1);
            }
            return;
        }
        prompt.append(value == null ? "" : value.toString());
    }

    /**
     * 按 {@code - key: value} 逐行输出一个 Map。
     *
     * <p>用于把解析后的结构化模板转成自然语言提示词里的可读段落。</p>
     *
     * @param prompt 输出缓冲
     * @param values 待输出 Map
     * @param indent 当前缩进层级
     */
    private void appendMap(StringBuilder prompt, Map<String, Object> values, int indent) {
        for (Map.Entry<String, Object> entry : values.entrySet()) {
            prompt.append(indent(indent)).append("- ").append(entry.getKey()).append(": ");
            appendValue(prompt, entry.getValue(), indent);
            prompt.append("\n");
        }
    }

    /**
     * 生成缩进空格串：每层两个空格。
     *
     * @param indent 缩进层级，负数按 0 处理（循环不执行）
     * @return 空格串
     */
    private String indent(int indent) {
        StringBuilder spaces = new StringBuilder();
        for (int i = 0; i < indent; i++) {
            spaces.append("  ");
        }
        return spaces.toString();
    }

    /**
     * 用中文分号拼接诊断消息。
     *
     * @param messages 消息列表，可为空
     * @return 拼接结果；列表为空时返回空串
     */
    private String join(List<String> messages) {
        StringBuilder joined = new StringBuilder();
        for (String message : messages) {
            if (joined.length() > 0) {
                joined.append("；");
            }
            joined.append(message);
        }
        return joined.toString();
    }

    /**
     * 查询条件归一化：去首尾空白并转小写。
     *
     * <p>固定用 {@link Locale#ROOT}，与检索索引的归一化保持一致，
     * 否则区域相关的转小写会让同一关键词在不同机器上匹配失败。</p>
     *
     * @param value 原始参数，可为 {@code null}
     * @return 归一化结果；{@code null} 返回空串
     */
    private String normalize(String value) {
        return value == null ? "" : value.trim().toLowerCase(Locale.ROOT);
    }

    /**
     * 判断字符串是否包含非空白字符。
     *
     * @param value 待判断文本，可为 {@code null}
     * @return {@code null} 或纯空白返回 {@code false}
     */
    private boolean hasText(String value) {
        return value != null && !value.trim().isEmpty();
    }
}
