package com.example.website.prompt.library;

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
import com.example.website.prompt.library.service.PromptLibraryServiceImpl;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.util.Arrays;
import java.util.Collections;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

/**
 * 提示词库业务实现 {@link PromptLibraryServiceImpl} 的单元测试。
 *
 * <p>{@link PromptLibraryDao} 全部用 Mockito mock，因此不连远程 MySQL，只验证业务规则：
 * meta 把统计行组装成「大分类 → 小分类 → 来源」的树并带上总数；search 会夹紧分页
 * （page 最小 1、size 限定 1..100、缺省为 1/48）、对 LIKE 通配符逐字转义
 * （{@code \}、{@code %}、{@code _} 各加一个反斜杠）、去掉过滤参数首尾空白、
 * 页码超出总数时不发列表查询、列表预览优先用 SQL 已算好的 {@code preview}；
 * detail 完成字段映射，id 为空或查不到时返回 null；create 覆盖必填校验与六条长度上限
 * （标题 512、小分类 128、正文 60000、标签 1000、来源链接 512、授权 255）、
 * 字段归一化与标签去重（半角/全角逗号都拆）、未知小分类归入 {@code other}，
 * 并固定写入 {@code manual} 来源、{@code imported} 状态和 {@code manual-} 前缀的 entry_key。</p>
 *
 * <p>校验失败必须发生在任何 DAO 调用之前，用例用 {@code verifyNoInteractions} 守住这一点，
 * 避免产生半条脏数据。隔离：除 mock DAO 外没有其它协作者，不联网。</p>
 */
class PromptLibraryServiceTest {

    private final PromptLibraryDao dao = mock(PromptLibraryDao.class);
    private final PromptLibraryServiceImpl service = new PromptLibraryServiceImpl(dao);

    @Test
    void metaAssemblesGroupsCategoriesAndSources() {
        when(dao.countAll()).thenReturn(3L);
        when(dao.selectGroupCounts()).thenReturn(
                Arrays.asList(groupStat("development-technology", "开发与技术", 2)));
        when(dao.selectCategoryCounts()).thenReturn(
                Arrays.asList(categoryStat("development-technology", "技术与编程", 2)));
        when(dao.selectSourceStats()).thenReturn(
                Arrays.asList(sourceStat("awesome", "Awesome", "imported", 3, "MIT", "摘要")));

        PromptMetaResponse meta = service.meta();

        assertThat(meta.isSuccess()).isTrue();
        assertThat(meta.getTotal()).isEqualTo(3L);
        assertThat(meta.getGroups()).hasSize(1);
        assertThat(meta.getGroups().get(0).getSlug()).isEqualTo("development-technology");
        assertThat(meta.getGroups().get(0).getCategories()).hasSize(1);
        assertThat(meta.getGroups().get(0).getCategories().get(0).getName()).isEqualTo("技术与编程");
        assertThat(meta.getSources()).hasSize(1);
        assertThat(meta.getSources().get(0).getSummary()).isEqualTo("摘要");
        assertThat(meta.getSources().get(0).getCount()).isEqualTo(3L);
    }

    @Test
    void searchClampsPageAndSizeAndEscapesLikeWildcards() {
        when(dao.countByFilter(any(), any(), any(), any(), any())).thenReturn(1L);
        when(dao.searchPage(any(), any(), any(), any(), any(), anyLong(), anyInt()))
                .thenReturn(Arrays.asList(entry()));

        PromptSearchRequest request = new PromptSearchRequest();
        request.setKeyword("50%_off\\x");
        request.setPage(0);
        request.setSize(999);
        PromptListResponse response = service.search(request);

        verify(dao).countByFilter("50\\%\\_off\\\\x", null, null, null, null);
        // page=0 夹到 1、size=999 夹到 100，offset 仍是 0。
        verify(dao).searchPage("50\\%\\_off\\\\x", null, null, null, null, 0L, 100);
        assertThat(response.getPage()).isEqualTo(1);
        assertThat(response.getSize()).isEqualTo(100);
        assertThat(response.getEntries()).hasSize(1);
        assertThat(response.getEntries().get(0).getTitle()).isEqualTo("小红书爆款");
        assertThat(response.getEntries().get(0).getTags()).containsExactly("小红书", "爆款");
        assertThat(response.getEntries().get(0).getPreview()).isEqualTo("preview...");
        assertThat(response.getEntries().get(0).getGroupName()).isEqualTo("写作与内容");
    }

    @Test
    void searchDefaultsPageAndSize() {
        when(dao.countByFilter(any(), any(), any(), any(), any())).thenReturn(0L);
        PromptListResponse response = service.search(new PromptSearchRequest());

        assertThat(response.getPage()).isEqualTo(1);
        assertThat(response.getSize()).isEqualTo(48);
        assertThat(response.getTotal()).isZero();
        assertThat(response.getEntries()).isEmpty();
        verify(dao, never()).searchPage(any(), any(), any(), any(), any(), anyLong(), anyInt());
    }

    @Test
    void searchClampsNegativePageAndSize() {
        when(dao.countByFilter(any(), any(), any(), any(), any())).thenReturn(1L);
        when(dao.searchPage(any(), any(), any(), any(), any(), anyLong(), anyInt()))
                .thenReturn(Collections.emptyList());

        PromptSearchRequest request = new PromptSearchRequest();
        request.setPage(-5);
        request.setSize(-1);

        PromptListResponse response = service.search(request);

        assertThat(response.getPage()).isEqualTo(1);
        assertThat(response.getSize()).isEqualTo(1);
        verify(dao).searchPage(null, null, null, null, null, 0L, 1);
    }

    @Test
    void searchPassesEscapedKeywordAllFiltersAndSecondPageOffset() {
        String escaped = "50\\%\\_off\\\\x";
        when(dao.countByFilter(escaped, "writing-content", "小红书", "manual", "imported")).thenReturn(100L);
        when(dao.searchPage(escaped, "writing-content", "小红书", "manual", "imported", 48L, 48))
                .thenReturn(Collections.singletonList(entry()));

        PromptSearchRequest request = new PromptSearchRequest();
        request.setKeyword(" 50%_off\\x ");
        request.setGroup(" writing-content ");
        request.setCategory(" 小红书 ");
        request.setSource(" manual ");
        request.setStatus(" imported ");
        request.setPage(2);
        request.setSize(48);

        PromptListResponse response = service.search(request);

        assertThat(response.getPage()).isEqualTo(2);
        assertThat(response.getSize()).isEqualTo(48);
        assertThat(response.getTotal()).isEqualTo(100L);
        assertThat(response.getEntries()).hasSize(1);
        verify(dao).countByFilter(escaped, "writing-content", "小红书", "manual", "imported");
        verify(dao).searchPage(escaped, "writing-content", "小红书", "manual", "imported", 48L, 48);
    }

    @Test
    void searchSkipsPageQueryWhenPageIsBeyondTotal() {
        when(dao.countByFilter(any(), any(), any(), any(), any())).thenReturn(10L);

        PromptSearchRequest request = new PromptSearchRequest();
        request.setPage(Integer.MAX_VALUE);
        request.setSize(100);

        PromptListResponse response = service.search(request);

        // page 取 Integer.MAX_VALUE 时 offset 会溢出，必须先用总数挡掉再查列表。
        assertThat(response.getPage()).isEqualTo(Integer.MAX_VALUE);
        assertThat(response.getSize()).isEqualTo(100);
        assertThat(response.getTotal()).isEqualTo(10L);
        assertThat(response.getEntries()).isEmpty();
        verify(dao, never()).searchPage(any(), any(), any(), any(), any(), anyLong(), anyInt());
    }

    @Test
    void searchUsesSqlPreviewWhenPresent() {
        when(dao.countByFilter(any(), any(), any(), any(), any())).thenReturn(1L);
        PromptEntry row = entry();
        row.setPrompt("这是很长的完整正文……");
        row.setPreview("来自 SQL 的预览");
        when(dao.searchPage(any(), any(), any(), any(), any(), anyLong(), anyInt()))
                .thenReturn(Arrays.asList(row));

        PromptListResponse response = service.search(new PromptSearchRequest());

        assertThat(response.getEntries().get(0).getPreview()).isEqualTo("来自 SQL 的预览");
    }

    @Test
    void detailReturnsMappedEntry() {
        when(dao.findById(7L)).thenReturn(entry());

        PromptDetailResponse detail = service.detail(7L);

        assertThat(detail).isNotNull();
        assertThat(detail.getEntry().getPrompt()).isEqualTo("完整正文");
        assertThat(detail.getEntry().getTags()).containsExactly("小红书", "爆款");
        assertThat(detail.getEntry().getSourceUrl()).isEqualTo("https://example.com");
    }

    @Test
    void detailReturnsNullWhenNotFound() {
        when(dao.findById(99L)).thenReturn(null);
        assertThat(service.detail(99L)).isNull();
        assertThat(service.detail(null)).isNull();
    }

    @Test
    void createInsertsManualEntryWithResolvedGroupAndNormalizedFields() {
        when(dao.findGroupSlugByCategory("小红书")).thenReturn("writing-content");
        when(dao.insert(any(PromptEntry.class))).thenAnswer(invocation -> {
            PromptEntry entry = invocation.getArgument(0);
            entry.setId(99L);
            return 1;
        });
        when(dao.findById(99L)).thenReturn(createdRow(99L, "writing-content"));

        PromptCreateRequest request = new PromptCreateRequest();
        request.setTitle("  新提示词  ");
        request.setCategory(" 小红书 ");
        request.setPrompt("  正文内容  ");
        request.setTags("标签A，标签B,标签A");
        request.setSourceUrl(" https://example.com/prompt ");
        request.setLicense("");

        PromptCreateResponse response = service.create(request);

        ArgumentCaptor<PromptEntry> captor = ArgumentCaptor.forClass(PromptEntry.class);
        verify(dao).insert(captor.capture());
        PromptEntry inserted = captor.getValue();
        assertThat(inserted.getTitle()).isEqualTo("新提示词");
        assertThat(inserted.getCategory()).isEqualTo("小红书");
        assertThat(inserted.getGroupSlug()).isEqualTo("writing-content");
        assertThat(inserted.getSourceId()).isEqualTo("manual");
        assertThat(inserted.getStatus()).isEqualTo("imported");
        assertThat(inserted.getEntryKey()).startsWith("manual-");
        // 全角逗号也要拆开，重复标签只保留第一次出现。
        assertThat(inserted.getTags()).isEqualTo("标签A,标签B");
        assertThat(inserted.getSourceUrl()).isEqualTo("https://example.com/prompt");
        assertThat(inserted.getLicense()).isEmpty();
        assertThat(inserted.getPrompt()).isEqualTo("正文内容");
        verify(dao).upsertManualSource();
        assertThat(response.isSuccess()).isTrue();
        assertThat(response.getEntry().getId()).isEqualTo(99L);
        assertThat(response.getEntry().getPrompt()).isEqualTo("正文内容");
    }

    @Test
    void createFallsBackToOtherGroupForUnknownCategory() {
        when(dao.findGroupSlugByCategory("全新分类")).thenReturn(null);
        when(dao.insert(any(PromptEntry.class))).thenAnswer(invocation -> {
            PromptEntry entry = invocation.getArgument(0);
            entry.setId(5L);
            return 1;
        });
        when(dao.findById(5L)).thenReturn(createdRow(5L, "other"));

        PromptCreateRequest request = new PromptCreateRequest();
        request.setTitle("新分类提示词");
        request.setCategory("全新分类");
        request.setPrompt("正文");

        service.create(request);

        ArgumentCaptor<PromptEntry> captor = ArgumentCaptor.forClass(PromptEntry.class);
        verify(dao).insert(captor.capture());
        assertThat(captor.getValue().getGroupSlug()).isEqualTo("other");
    }

    @Test
    void createRejectsMissingRequiredFields() {
        assertThatThrownBy(() -> service.create(null))
                .isInstanceOf(IllegalArgumentException.class);

        PromptCreateRequest request = new PromptCreateRequest();
        assertThatThrownBy(() -> service.create(request))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("标题");

        request.setTitle("标题");
        assertThatThrownBy(() -> service.create(request))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("小分类");

        request.setCategory("分类");
        assertThatThrownBy(() -> service.create(request))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("正文");
    }

    @Test
    void createRejectsOverlongTitle() {
        PromptCreateRequest request = new PromptCreateRequest();
        StringBuilder title = new StringBuilder();
        for (int i = 0; i < 513; i++) {
            title.append("a");
        }
        request.setTitle(title.toString());
        request.setCategory("分类");
        request.setPrompt("正文");

        assertThatThrownBy(() -> service.create(request))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("512");
    }

    @Test
    void createRejectsOverlongOptionalFields() {
        PromptCreateRequest tagsRequest = validCreateRequest();
        tagsRequest.setTags(repeat('t', 501) + "," + repeat('t', 501));
        assertThatThrownBy(() -> service.create(tagsRequest))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("标签")
                .hasMessageContaining("1000");

        PromptCreateRequest sourceUrlRequest = validCreateRequest();
        sourceUrlRequest.setSourceUrl(repeat('u', 513));
        assertThatThrownBy(() -> service.create(sourceUrlRequest))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("来源链接")
                .hasMessageContaining("512");

        PromptCreateRequest licenseRequest = validCreateRequest();
        licenseRequest.setLicense(repeat('l', 256));
        assertThatThrownBy(() -> service.create(licenseRequest))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("授权")
                .hasMessageContaining("255");

        // 校验失败不能碰 DAO，否则会留下半条脏数据。
        verifyNoInteractions(dao);
    }

    @Test
    void createAcceptsOptionalFieldsAtMaxLength() {
        when(dao.findGroupSlugByCategory("分类")).thenReturn("writing-content");
        when(dao.insert(any(PromptEntry.class))).thenAnswer(invocation -> {
            PromptEntry entry = invocation.getArgument(0);
            entry.setId(11L);
            return 1;
        });
        when(dao.findById(11L)).thenReturn(createdRow(11L, "writing-content"));

        String tags = repeat('t', 1000);
        String sourceUrl = repeat('u', 512);
        String license = repeat('l', 255);
        PromptCreateRequest request = validCreateRequest();
        request.setTags(tags);
        request.setSourceUrl(sourceUrl);
        request.setLicense(license);

        service.create(request);

        ArgumentCaptor<PromptEntry> captor = ArgumentCaptor.forClass(PromptEntry.class);
        verify(dao).insert(captor.capture());
        assertThat(captor.getValue().getTags()).isEqualTo(tags);
        assertThat(captor.getValue().getSourceUrl()).isEqualTo(sourceUrl);
        assertThat(captor.getValue().getLicense()).isEqualTo(license);
    }

    @Test
    void createRejectsOverlongCategoryAndPrompt() {
        PromptCreateRequest categoryRequest = validCreateRequest();
        categoryRequest.setCategory(repeat('c', 129));
        assertThatThrownBy(() -> service.create(categoryRequest))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("128");

        PromptCreateRequest promptRequest = validCreateRequest();
        promptRequest.setPrompt(repeat('p', 60001));
        assertThatThrownBy(() -> service.create(promptRequest))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("60000");

        verifyNoInteractions(dao);
    }

    /** 只填标题、小分类、正文三个必填字段的最小合法请求。 */
    private PromptCreateRequest validCreateRequest() {
        PromptCreateRequest request = new PromptCreateRequest();
        request.setTitle("标题");
        request.setCategory("分类");
        request.setPrompt("正文");
        return request;
    }

    /** 生成恰好 {@code count} 个字符的字段值，用来卡在长度上限与超限之间。 */
    private String repeat(char value, int count) {
        char[] chars = new char[count];
        Arrays.fill(chars, value);
        return new String(chars);
    }

    /** 模拟 insert 之后按回填 id 回查出来的整行，含大分类名与来源名。 */
    private PromptEntry createdRow(Long id, String groupSlug) {
        PromptEntry entry = new PromptEntry();
        entry.setId(id);
        entry.setEntryKey("manual-1");
        entry.setSourceId("manual");
        entry.setSourceName("手动添加");
        entry.setTitle("新提示词");
        entry.setCategory("小红书");
        entry.setGroupSlug(groupSlug);
        entry.setGroupName("写作与内容");
        entry.setTags("标签A,标签B");
        entry.setLicense("");
        entry.setStatus("imported");
        entry.setSourceUrl("https://example.com/prompt");
        entry.setPrompt("正文内容");
        return entry;
    }

    /** 列表与详情共用的行数据：tags 是逗号串，preview 已由 SQL 截好。 */
    private PromptEntry entry() {
        PromptEntry entry = new PromptEntry();
        entry.setId(1L);
        entry.setTitle("小红书爆款");
        entry.setCategory("小红书");
        entry.setGroupSlug("writing-content");
        entry.setGroupName("写作与内容");
        entry.setSourceName("Prompt123");
        entry.setTags("小红书,爆款");
        entry.setLicense("授权");
        entry.setStatus("imported");
        entry.setSourceUrl("https://example.com");
        entry.setPrompt("完整正文");
        entry.setPreview("preview...");
        return entry;
    }

    /** 构造一行大分类统计，{@code count} 是该大分类下的条目数。 */
    private PromptGroupStat groupStat(String slug, String name, long count) {
        PromptGroupStat stat = new PromptGroupStat();
        stat.setSlug(slug);
        stat.setName(name);
        stat.setCount(count);
        return stat;
    }

    /** 构造一行小分类统计，带所属大分类 slug，用于验证 meta 的嵌套关系。 */
    private PromptCategoryStat categoryStat(String groupSlug, String category, long count) {
        PromptCategoryStat stat = new PromptCategoryStat();
        stat.setGroupSlug(groupSlug);
        stat.setCategory(category);
        stat.setCount(count);
        return stat;
    }

    /** 构造一行来源统计，含状态、条目数、授权与摘要。 */
    private PromptSourceStat sourceStat(String id, String name, String status, long count, String license, String summary) {
        PromptSourceStat stat = new PromptSourceStat();
        stat.setSourceId(id);
        stat.setName(name);
        stat.setStatus(status);
        stat.setCount(count);
        stat.setLicense(license);
        stat.setSummary(summary);
        return stat;
    }
}