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
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

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
        when(dao.searchPage(any(), any(), any(), any(), any(), anyInt(), anyInt()))
                .thenReturn(Arrays.asList(entry()));

        PromptSearchRequest request = new PromptSearchRequest();
        request.setKeyword("50%_off\\x");
        request.setPage(0);
        request.setSize(999);
        PromptListResponse response = service.search(request);

        verify(dao).countByFilter("50\\%\\_off\\\\x", null, null, null, null);
        verify(dao).searchPage("50\\%\\_off\\\\x", null, null, null, null, 0, 100);
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
        when(dao.searchPage(any(), any(), any(), any(), any(), anyInt(), anyInt()))
                .thenReturn(Collections.emptyList());

        PromptListResponse response = service.search(new PromptSearchRequest());

        assertThat(response.getPage()).isEqualTo(1);
        assertThat(response.getSize()).isEqualTo(48);
        assertThat(response.getTotal()).isZero();
        assertThat(response.getEntries()).isEmpty();
    }

    @Test
    void searchUsesSqlPreviewWhenPresent() {
        when(dao.countByFilter(any(), any(), any(), any(), any())).thenReturn(1L);
        PromptEntry row = entry();
        row.setPrompt("这是很长的完整正文……");
        row.setPreview("来自 SQL 的预览");
        when(dao.searchPage(any(), any(), any(), any(), any(), anyInt(), anyInt()))
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

    private PromptGroupStat groupStat(String slug, String name, long count) {
        PromptGroupStat stat = new PromptGroupStat();
        stat.setSlug(slug);
        stat.setName(name);
        stat.setCount(count);
        return stat;
    }

    private PromptCategoryStat categoryStat(String groupSlug, String category, long count) {
        PromptCategoryStat stat = new PromptCategoryStat();
        stat.setGroupSlug(groupSlug);
        stat.setCategory(category);
        stat.setCount(count);
        return stat;
    }

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