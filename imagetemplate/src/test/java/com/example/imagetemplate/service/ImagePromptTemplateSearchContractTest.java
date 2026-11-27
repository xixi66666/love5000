package com.example.imagetemplate.service;

import com.example.imagetemplate.dto.ImageTemplateMetaResponse;
import com.example.imagetemplate.dto.ImageTemplatePageResponse;
import com.example.imagetemplate.dto.ImageTemplateQuery;
import com.example.imagetemplate.dto.ImageTemplateSummaryResponse;
import com.example.imagetemplate.dto.TemplateCategoryResponse;
import com.example.imagetemplate.dto.TemplateFunctionCategoryResponse;
import com.example.imagetemplate.dto.TemplateFunctionSceneResponse;
import com.example.imagetemplate.model.ImagePromptTemplate;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * 搜索与元数据的对外契约测试。
 *
 * <p>以真实聚合结果（47 条精选 + 4409 条大库 = 4456 条）为基准，锁定前端依赖的行为：精选
 * 模板整体排在前面且跨页顺序稳定、默认分页为 48、中文关键词与 ASCII 均忽略大小写、一级
 * 功能与二级场景同时支持 slug 和中文名、{@code imageOnly} 与 meta 的
 * {@code imageRelatedCount} 一致、越界页码被夹取而不是报错，以及分类、来源、一级功能的计数
 * 之和必须等于总数、二级场景计数之和必须等于所属一级功能。最后一个用例还验证 meta 与分类
 * 列表每次返回独立快照，调用方修改不会污染下一次响应。</p>
 *
 * <p>隔离手段：服务层用真实实现读取 classpath JSON，不启动 Spring 上下文、不访问数据库或
 * 网络；关键词期望值由 {@link #expectedKeywordIds(String)} 独立重算，不复用被测实现的
 * 匹配逻辑。</p>
 */
class ImagePromptTemplateSearchContractTest {

    private static ImagePromptTemplateService service;

    private static List<ImagePromptTemplate> allTemplates;

    @BeforeAll
    static void setUp() {
        ObjectMapper objectMapper = new ObjectMapper();
        service = new ImagePromptTemplateService(
                objectMapper,
                new PromptLibraryLoader(objectMapper),
                new ImagePromptTemplateAdapter(),
                new TemplateFunctionClassifier());
        allTemplates = service.listTemplates(null, null);
    }

    @Test
    void pagesTheFullAggregateInCuratedFirstOrder() {
        List<ImageTemplateSummaryResponse> pages =
                collectAll(new ImageTemplateQuery());

        assertThat(pages).hasSize(4456);
        assertThat(ids(pages)).doesNotHaveDuplicates();
        assertThat(ids(pages)).containsExactlyElementsOf(templateIds());
        assertThat(pages.subList(0, 47)).allMatch(ImageTemplateSummaryResponse::isCurated);
        // 精选库固定 47 条并整体置顶，第 48 条起才是可编辑的大库条目。
        assertThat(pages.get(47).isCurated()).isFalse();

        ImageTemplatePageResponse defaults = service.search(new ImageTemplateQuery());
        assertThat(defaults.getTotal()).isEqualTo(4456);
        assertThat(defaults.getPage()).isEqualTo(1);
        assertThat(defaults.getSize()).isEqualTo(48);
        assertThat(defaults.getTemplates()).hasSize(48);
        assertThat(defaults.isHasMore()).isTrue();
        assertThat(defaults.getLibraryStatus()).isEqualTo("READY");
        assertThat(defaults.getMessage()).isEmpty();
    }

    @Test
    void searchesChineseKeywordsAcrossCuratedAndLibraryPrompts() {
        List<String> expectedHeadshots = expectedKeywordIds("头像");
        assertThat(expectedHeadshots)
                .contains("id-photo-headshot", "social-avatar");
        ImageTemplatePageResponse headshotPage = service.search(keywordQuery("头像"));
        assertThat(headshotPage.getTotal()).isEqualTo(expectedHeadshots.size());
        assertThat(ids(headshotPage.getTemplates()))
                .contains("id-photo-headshot", "social-avatar");
        assertThat(ids(collectAll(keywordQuery("头像"))))
                .containsExactlyElementsOf(expectedHeadshots);

        List<String> expectedInk = expectedKeywordIds("水墨");
        assertThat(expectedInk).isNotEmpty();
        assertThat(service.search(keywordQuery("  水墨  ")).getTotal())
                .isEqualTo(expectedInk.size());
        assertThat(ids(collectAll(keywordQuery("水墨"))))
                .containsExactlyElementsOf(expectedInk);

        List<String> expectedLogo = expectedKeywordIds("logo");
        assertThat(expectedLogo).isNotEmpty();
        assertThat(service.search(keywordQuery("LOGO")).getTotal())
                .isEqualTo(expectedLogo.size());
        assertThat(ids(collectAll(keywordQuery("logo"))))
                .containsExactlyElementsOf(expectedLogo);
    }

    @Test
    void appliesTwoLevelFunctionFiltersBySlugAndDisplayName() {
        ImageTemplateMetaResponse meta = service.getMeta();
        TemplateFunctionCategoryResponse category = meta.getFunctionCategories().stream()
                .filter(item -> item.getCount() > 0)
                .filter(item -> item.getScenes().stream()
                        .anyMatch(scene -> scene.getCount() > 0))
                .findFirst()
                .orElseThrow(AssertionError::new);
        TemplateFunctionSceneResponse scene = category.getScenes().stream()
                .filter(item -> item.getCount() > 0)
                .findFirst()
                .orElseThrow(AssertionError::new);

        assertThat(service.search(functionCategoryQuery(category.getSlug())).getTotal())
                .isEqualTo(category.getCount());
        assertThat(service.search(functionCategoryQuery(category.getName())).getTotal())
                .isEqualTo(category.getCount());

        ImageTemplateQuery sceneQuery = new ImageTemplateQuery();
        sceneQuery.setPage(1);
        sceneQuery.setSize(1);
        sceneQuery.setFunctionCategory(category.getSlug());
        sceneQuery.setFunctionScene(scene.getSlug());
        assertThat(service.search(sceneQuery).getTotal()).isEqualTo(scene.getCount());

        sceneQuery.setFunctionScene(scene.getName());
        assertThat(service.search(sceneQuery).getTotal()).isEqualTo(scene.getCount());

        ImageTemplateQuery unknown = new ImageTemplateQuery();
        unknown.setFunctionCategory("function-does-not-exist");
        unknown.setFunctionScene("scene-does-not-exist");
        assertThat(service.search(unknown).getTotal()).isZero();
        assertThat(service.search(unknown).getTemplates()).isEmpty();
    }

    @Test
    void appliesImageOnlyFilterAgainstTheMetaCount() {
        ImageTemplateMetaResponse meta = service.getMeta();
        ImageTemplateQuery all = new ImageTemplateQuery();
        all.setPage(1);
        all.setSize(1);
        assertThat(service.search(all).getTotal()).isEqualTo(meta.getTotal());

        ImageTemplateQuery imageOnly = new ImageTemplateQuery();
        imageOnly.setPage(1);
        imageOnly.setSize(1);
        imageOnly.setImageOnly(true);
        ImageTemplatePageResponse page = service.search(imageOnly);
        assertThat(page.getTotal()).isEqualTo(meta.getImageRelatedCount());
        assertThat(page.getTotal()).isGreaterThan(0);
        assertThat(page.getTotal()).isLessThan(meta.getTotal());
        assertThat(collectAll(imageOnly))
                .hasSize(meta.getImageRelatedCount())
                .allMatch(ImageTemplateSummaryResponse::isImageRelated);
        assertThat(allTemplates).anyMatch(ImagePromptTemplate::isImageRelated);
        assertThat(allTemplates).anyMatch(template -> !template.isImageRelated());
    }

    @Test
    void clampsOutOfRangePagesAndEchoesTheRequest() {
        int total = service.getMeta().getTotal();
        int lastPage = (total + 99) / 100;
        ImageTemplatePageResponse last = service.search(query(lastPage, 100));
        assertThat(last.getTemplates())
                .hasSize(total - (lastPage - 1) * 100);
        assertThat(last.isHasMore()).isFalse();
        assertThat(last.getPage()).isEqualTo(lastPage);
        assertThat(last.getSize()).isEqualTo(100);
        assertThat(last.getTotal()).isEqualTo(total);

        ImageTemplatePageResponse beyond = service.search(query(lastPage + 1, 100));
        assertThat(beyond.getTemplates()).isEmpty();
        assertThat(beyond.getTotal()).isEqualTo(total);
        assertThat(beyond.getPage()).isEqualTo(lastPage + 1);
        assertThat(beyond.getSize()).isEqualTo(100);
        assertThat(beyond.isHasMore()).isFalse();

        // 页码取 Integer.MAX_VALUE，验证 (page - 1) * size 的偏移计算不会溢出成负数。
        ImageTemplatePageResponse overflow = service.search(
                query(Integer.MAX_VALUE, 100));
        assertThat(overflow.getTemplates()).isEmpty();
        assertThat(overflow.getTotal()).isEqualTo(total);
        assertThat(overflow.getPage()).isEqualTo(Integer.MAX_VALUE);
        assertThat(overflow.isHasMore()).isFalse();

        int filteredTotal = expectedKeywordIds("水墨").size();
        ImageTemplatePageResponse filteredBeyond =
                service.search(keywordPageQuery("水墨", 2, 100));
        assertThat(filteredBeyond.getTotal()).isEqualTo(filteredTotal);
        assertThat(filteredBeyond.getTemplates()).isEmpty();
        assertThat(filteredBeyond.isHasMore()).isFalse();

        assertThatThrownBy(() -> service.search(query(0, 48)))
                .isInstanceOf(ImageTemplateQueryValidationException.class);
        assertThatThrownBy(() -> service.search(query(-1, 48)))
                .isInstanceOf(ImageTemplateQueryValidationException.class);
        assertThatThrownBy(() -> service.search(query(1, 0)))
                .isInstanceOf(ImageTemplateQueryValidationException.class);
        assertThatThrownBy(() -> service.search(query(1, 101)))
                .isInstanceOf(ImageTemplateQueryValidationException.class);
    }

    @Test
    void keepsMetaCategoryAndFunctionCountsClosed() {
        ImageTemplateMetaResponse meta = service.getMeta();

        assertThat(meta.getTotal()).isEqualTo(4456);
        assertThat(meta.getCuratedCount()).isEqualTo(47);
        assertThat(meta.getLibraryCount()).isEqualTo(4409);
        assertThat(meta.getStatus().getStatus()).isEqualTo("READY");
        assertThat(meta.getCategories().stream().mapToInt(
                TemplateCategoryResponse::getCount).sum()).isEqualTo(meta.getTotal());
        assertThat(meta.getFunctionCategories().stream().mapToInt(
                TemplateFunctionCategoryResponse::getCount).sum()).isEqualTo(meta.getTotal());
        assertThat(meta.getSources().stream().mapToInt(
                source -> source.getCount()).sum()).isEqualTo(meta.getTotal());

        for (TemplateFunctionCategoryResponse category : meta.getFunctionCategories()) {
            assertThat(category.getScenes().stream().mapToInt(
                    TemplateFunctionSceneResponse::getCount).sum())
                    .as("scenes of %s", category.getSlug())
                    .isEqualTo(category.getCount());
        }

        ImageTemplatePageResponse page = service.search(new ImageTemplateQuery());
        assertThat(page.getLibraryStatus()).isEqualTo(meta.getStatus().getStatus());
        assertThat(page.getMessage()).isEqualTo(meta.getStatus().getMessage());

        for (TemplateCategoryResponse category : meta.getCategories()) {
            ImageTemplateQuery bySlug = new ImageTemplateQuery();
            bySlug.setPage(1);
            bySlug.setSize(1);
            bySlug.setCategory(category.getSlug());
            assertThat(service.search(bySlug).getTotal())
                    .as("category slug %s", category.getSlug())
                    .isEqualTo(category.getCount());

            ImageTemplateQuery byName = new ImageTemplateQuery();
            byName.setPage(1);
            byName.setSize(1);
            byName.setCategory(category.getName());
            assertThat(service.search(byName).getTotal())
                    .as("category name %s", category.getName())
                    .isEqualTo(category.getCount());
        }

        for (TemplateFunctionCategoryResponse category : meta.getFunctionCategories()) {
            assertThat(service.search(functionCategoryQuery(category.getSlug())).getTotal())
                    .as("function category %s", category.getSlug())
                    .isEqualTo(category.getCount());
            for (TemplateFunctionSceneResponse scene : category.getScenes()) {
                ImageTemplateQuery byScene = new ImageTemplateQuery();
                byScene.setPage(1);
                byScene.setSize(1);
                byScene.setFunctionCategory(category.getSlug());
                byScene.setFunctionScene(scene.getSlug());
                assertThat(service.search(byScene).getTotal())
                        .as("scene %s/%s", category.getSlug(), scene.getSlug())
                        .isEqualTo(scene.getCount());
            }
        }
    }

    @Test
    void returnsIndependentCategorySnapshots() {
        ImageTemplateMetaResponse first = service.getMeta();
        int originalCount = first.getCategories().get(0).getCount();
        first.getCategories().get(0).setCount(originalCount + 1);
        first.getCategories().get(0).setName("被外部修改");
        assertThat(first.getCategories().get(0).getCount()).isEqualTo(originalCount + 1);

        ImageTemplateMetaResponse second = service.getMeta();
        assertThat(second.getCategories().get(0).getCount()).isEqualTo(originalCount);
        assertThat(second.getCategories().get(0).getName())
                .isNotEqualTo("被外部修改");

        List<TemplateCategoryResponse> listed = service.listCategories();
        listed.get(0).setCount(originalCount + 2);
        assertThat(service.listCategories().get(0).getCount()).isEqualTo(originalCount);
    }

    @Test
    void listTemplatesAndSearchUseTheSameFilters() {
        assertThat(service.listTemplates(null, null)).hasSize(4456);

        for (TemplateCategoryResponse category : service.getMeta().getCategories()) {
            ImageTemplateQuery query = new ImageTemplateQuery();
            query.setPage(1);
            query.setSize(1);
            query.setCategory(category.getSlug());
            assertThat(service.listTemplates(category.getSlug(), null)).hasSize(
                    service.search(query).getTotal());
        }

        int headshotTotal = service.search(keywordQuery("头像")).getTotal();
        assertThat(service.listTemplates(null, "头像")).hasSize(headshotTotal);
    }

    private static ImageTemplateQuery query(int page, int size) {
        ImageTemplateQuery query = new ImageTemplateQuery();
        query.setPage(page);
        query.setSize(size);
        return query;
    }

    private static ImageTemplateQuery keywordQuery(String keyword) {
        ImageTemplateQuery query = new ImageTemplateQuery();
        query.setPage(1);
        query.setSize(48);
        query.setKeyword(keyword);
        return query;
    }

    private static ImageTemplateQuery keywordPageQuery(String keyword, int page, int size) {
        ImageTemplateQuery query = query(page, size);
        query.setKeyword(keyword);
        return query;
    }

    private static ImageTemplateQuery functionCategoryQuery(String category) {
        ImageTemplateQuery query = new ImageTemplateQuery();
        query.setPage(1);
        query.setSize(1);
        query.setFunctionCategory(category);
        return query;
    }

    /**
     * 以 {@code size=100} 逐页翻完整个结果集，用于验证分页边界与跨页顺序。
     *
     * <p>会就地修改传入 query 的 page 与 size；{@code hasMore=false} 视为结束，并断言总页数
     * 小于 100，防止分页标志写错时用例陷入死循环。</p>
     */
    private static List<ImageTemplateSummaryResponse> collectAll(ImageTemplateQuery base) {
        List<ImageTemplateSummaryResponse> all =
                new ArrayList<ImageTemplateSummaryResponse>();
        base.setSize(100);
        for (int page = 1; ; page++) {
            base.setPage(page);
            ImageTemplatePageResponse response = service.search(base);
            all.addAll(response.getTemplates());
            if (!response.isHasMore()) {
                assertThat(page).isLessThan(100);
                return all;
            }
        }
    }

    private static List<String> ids(List<ImageTemplateSummaryResponse> templates) {
        List<String> ids = new ArrayList<String>();
        for (ImageTemplateSummaryResponse template : templates) {
            ids.add(template.getId());
        }
        return ids;
    }

    private static List<String> templateIds() {
        List<String> ids = new ArrayList<String>();
        for (ImagePromptTemplate template : allTemplates) {
            ids.add(template.getId());
        }
        return ids;
    }

    /**
     * 按文档约定的关键词字段集合独立重算期望 ID 列表。
     *
     * <p>字段为标题、摘要、分类、来源名、Prompt 正文与全部标签，统一转小写后做包含匹配。
     * 这里刻意不复用 {@link TemplateSearchIndex}，以便发现实现漏掉某个字段的回归。</p>
     */
    private static List<String> expectedKeywordIds(String keyword) {
        String needle = keyword.trim().toLowerCase(Locale.ROOT);
        List<String> ids = new ArrayList<String>();
        for (ImagePromptTemplate template : allTemplates) {
            StringBuilder haystack = new StringBuilder();
            haystack.append(template.getTitle()).append(' ')
                    .append(template.getSummary()).append(' ')
                    .append(template.getCategory()).append(' ')
                    .append(template.getSourceName()).append(' ')
                    .append(template.getPromptTemplate());
            if (template.getTags() != null) {
                for (String tag : template.getTags()) {
                    haystack.append(' ').append(tag);
                }
            }
            if (haystack.toString().toLowerCase(Locale.ROOT).contains(needle)) {
                ids.add(template.getId());
            }
        }
        return ids;
    }
}
