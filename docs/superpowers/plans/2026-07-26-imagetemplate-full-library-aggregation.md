# Imagetemplate Full Prompt Library Aggregation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Prompt Console 的 4409 条提示词与 imagetemplate 的 47 条精选模板聚合为可独立打包、可分页检索和可直接进入图片生成流程的 4456 条模板库。

**Architecture:** Maven 在构建 imagetemplate 时把 website 中的唯一大库源文件复制进模块 classpath；后端分别负责加载、适配、聚合、过滤和分页，并用摘要 DTO 与详情 DTO 隔离大 Prompt。原生前端通过元数据、分页列表和按需详情接口实现来源筛选、分类筛选、仅图片相关、300ms 搜索防抖和加载更多，同时保留现有四场景工作流。

**Tech Stack:** Java 8、Spring Boot 2.6.13、Jackson、Spring MVC、Maven Resources、JUnit 5、MockMvc、AssertJ、原生 HTML/CSS/JavaScript

---

## 文件结构

新增文件：

- `imagetemplate/src/main/java/com/example/imagetemplate/model/PromptLibraryCatalog.java`：Prompt Console 大库根模型。
- `imagetemplate/src/main/java/com/example/imagetemplate/model/PromptLibrarySource.java`：大库来源模型。
- `imagetemplate/src/main/java/com/example/imagetemplate/model/PromptLibraryEntry.java`：大库条目模型。
- `imagetemplate/src/main/java/com/example/imagetemplate/model/PromptLibraryLoadResult.java`：大库加载结果和错误信息。
- `imagetemplate/src/main/java/com/example/imagetemplate/model/LibraryAggregationStatus.java`：聚合完整性状态。
- `imagetemplate/src/main/java/com/example/imagetemplate/dto/ImageTemplateQuery.java`：分页和筛选参数。
- `imagetemplate/src/main/java/com/example/imagetemplate/dto/ImageTemplateSummaryResponse.java`：列表摘要 DTO。
- `imagetemplate/src/main/java/com/example/imagetemplate/dto/ImageTemplatePageResponse.java`：分页响应 DTO。
- `imagetemplate/src/main/java/com/example/imagetemplate/dto/ImageTemplateMetaResponse.java`：来源、分类和加载状态 DTO。
- `imagetemplate/src/main/java/com/example/imagetemplate/dto/TemplateSourceResponse.java`：来源计数 DTO。
- `imagetemplate/src/main/java/com/example/imagetemplate/service/PromptLibraryLoader.java`：读取和验证 4409 条大库数据。
- `imagetemplate/src/main/java/com/example/imagetemplate/service/ImagePromptTemplateAdapter.java`：将大库条目适配为图片模板并生成稳定 ID。
- `imagetemplate/src/main/java/com/example/imagetemplate/service/ImageTemplateQueryValidationException.java`：稳定的分页参数错误。
- `imagetemplate/src/test/java/com/example/imagetemplate/service/PromptLibraryLoaderTest.java`：资源加载和降级测试。
- `imagetemplate/src/test/java/com/example/imagetemplate/service/ImagePromptTemplateAdapterTest.java`：适配、ID 和图片相关判定测试。
- `imagetemplate/src/test/java/com/example/imagetemplate/controller/ImagePromptTemplateControllerTest.java`：分页、元数据、详情和参数错误接口测试。
- `imagetemplate/src/test/java/com/example/imagetemplate/PromptLibraryPackagingTest.java`：构建资源复制契约。

修改文件：

- `imagetemplate/pom.xml`：把 website 大库复制到 imagetemplate classpath。
- `imagetemplate/src/main/java/com/example/imagetemplate/model/ImagePromptTemplate.java`：增加来源、类型、精选和图片相关字段。
- `imagetemplate/src/main/java/com/example/imagetemplate/service/ImagePromptTemplateService.java`：聚合、分页、过滤、详情和 DIRECT 渲染。
- `imagetemplate/src/main/java/com/example/imagetemplate/controller/ImagePromptTemplateController.java`：分页列表和元数据接口。
- `imagetemplate/src/test/java/com/example/imagetemplate/service/ImagePromptTemplateServiceTest.java`：4456 条聚合行为测试。
- `imagetemplate/src/test/java/com/example/imagetemplate/ImageTemplateHomepageStaticAssetsTest.java`：新前端控件和行为契约。
- `imagetemplate/src/main/resources/static/index.html`：来源、分类、图片开关、加载状态和加载更多。
- `imagetemplate/src/main/resources/static/css/app.css`：聚合筛选器、徽章、告警和分页样式。
- `imagetemplate/src/main/resources/static/js/app.js`：分页状态、元数据、300ms 防抖和详情按需加载。
- `README.md`、`AGENTS.md`、`imagetemplate/README.md`、`imagetemplate/AGENTS.md`：同步数据源、数量、API、构建和测试说明。

### Task 1: 建立构建时资源共享契约

**Files:**

- Modify: `imagetemplate/pom.xml`
- Create: `imagetemplate/src/test/java/com/example/imagetemplate/PromptLibraryPackagingTest.java`

- [ ] **Step 1: 写入会失败的 classpath 资源测试**

创建测试，明确目标路径和条目数量：

```java
package com.example.imagetemplate;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;

import static org.assertj.core.api.Assertions.assertThat;

class PromptLibraryPackagingTest {

    @Test
    void promptConsoleLibraryIsCopiedIntoImageTemplateClasspath() throws Exception {
        ClassPathResource resource =
                new ClassPathResource("templates/prompt-console/prompt-library.json");

        assertThat(resource.exists()).isTrue();
        JsonNode root = new ObjectMapper().readTree(resource.getInputStream());
        assertThat(root.path("sources").size()).isEqualTo(6);
        assertThat(root.path("entries").size()).isEqualTo(4409);
    }
}
```

- [ ] **Step 2: 运行测试并确认资源尚不存在**

Run:

```powershell
mvn -pl imagetemplate -am '-Dtest=PromptLibraryPackagingTest' -DfailIfNoTests=false test
```

Expected: `PromptLibraryPackagingTest` FAIL，`resource.exists()` 为 `false`。

- [ ] **Step 3: 在 Maven resources 中复制唯一源文件**

在 `imagetemplate/pom.xml` 的 `<build>` 下、`<plugins>` 前加入：

```xml
<resources>
  <resource>
    <directory>src/main/resources</directory>
  </resource>
  <resource>
    <directory>${project.basedir}/../website/src/main/resources/static/prompt-console/data</directory>
    <includes>
      <include>prompt-library.json</include>
    </includes>
    <targetPath>templates/prompt-console</targetPath>
    <filtering>false</filtering>
  </resource>
</resources>
```

- [ ] **Step 4: 运行资源测试并检查 target 输出**

Run:

```powershell
mvn -pl imagetemplate -am '-Dtest=PromptLibraryPackagingTest' -DfailIfNoTests=false test
Get-Item imagetemplate/target/classes/templates/prompt-console/prompt-library.json
```

Expected: 测试 PASS，目标文件存在且大小大于 12MB。

- [ ] **Step 5: 提交资源共享契约**

```powershell
git add -- imagetemplate/pom.xml imagetemplate/src/test/java/com/example/imagetemplate/PromptLibraryPackagingTest.java
git commit -m "build(imagetemplate): package shared prompt library"
```

### Task 2: 加载并验证 Prompt Console 大库

**Files:**

- Create: `imagetemplate/src/main/java/com/example/imagetemplate/model/PromptLibraryCatalog.java`
- Create: `imagetemplate/src/main/java/com/example/imagetemplate/model/PromptLibrarySource.java`
- Create: `imagetemplate/src/main/java/com/example/imagetemplate/model/PromptLibraryEntry.java`
- Create: `imagetemplate/src/main/java/com/example/imagetemplate/model/PromptLibraryLoadResult.java`
- Create: `imagetemplate/src/main/java/com/example/imagetemplate/service/PromptLibraryLoader.java`
- Create: `imagetemplate/src/test/java/com/example/imagetemplate/service/PromptLibraryLoaderTest.java`

- [ ] **Step 1: 写入真实资源、非法 JSON 和字段缺失测试**

测试必须覆盖以下断言：

```java
@Test
void loadsAllPromptConsoleEntriesAndSources() {
    PromptLibraryLoadResult result = loader.loadDefault();

    assertThat(result.getEntries()).hasSize(4409);
    assertThat(result.getSources()).hasSize(6);
    assertThat(result.getErrorCount()).isZero();
    assertThat(result.getMessage()).isEmpty();
}

@Test
void reportsMalformedJsonWithoutThrowingAwayProcessAvailability() {
    PromptLibraryLoadResult result =
            loader.load(new ByteArrayResource("{invalid".getBytes(StandardCharsets.UTF_8)));

    assertThat(result.getEntries()).isEmpty();
    assertThat(result.getErrorCount()).isGreaterThan(0);
    assertThat(result.getMessage()).contains("解析");
}

@Test
void skipsInvalidRowsAndReportsDegradedCount() {
    String json = "{\"sources\":[],\"entries\":["
            + "{\"id\":\"ok\",\"sourceId\":\"source\",\"sourceName\":\"Source\","
            + "\"title\":\"有效\",\"category\":\"测试\",\"tags\":[],\"prompt\":\"完整提示词\"},"
            + "{\"id\":\"bad\",\"sourceId\":\"source\",\"sourceName\":\"Source\","
            + "\"title\":\"缺少 Prompt\",\"category\":\"测试\",\"tags\":[]}"
            + "]}";

    PromptLibraryLoadResult result =
            loader.load(new ByteArrayResource(json.getBytes(StandardCharsets.UTF_8)));

    assertThat(result.getEntries()).extracting("id").containsExactly("ok");
    assertThat(result.getErrorCount()).isEqualTo(1);
    assertThat(result.getMessage()).contains("1");
}
```

- [ ] **Step 2: 运行加载器测试并确认编译失败**

Run:

```powershell
mvn -pl imagetemplate -am '-Dtest=PromptLibraryLoaderTest' -DfailIfNoTests=false test
```

Expected: FAIL，加载模型和 `PromptLibraryLoader` 尚不存在。

- [ ] **Step 3: 实现 Jackson 数据模型**

三个 JSON 模型使用 JavaBean 字段和 getter/setter。字段定义固定为：

```java
public class PromptLibraryCatalog {
    private String generatedAt;
    private boolean authorizedByUser;
    private List<PromptLibrarySource> sources = new ArrayList<PromptLibrarySource>();
    private List<PromptLibraryEntry> entries = new ArrayList<PromptLibraryEntry>();
}

public class PromptLibrarySource {
    private String id;
    private String name;
    private String url;
    private String license;
    private String summary;
    private List<String> categories = new ArrayList<String>();
    private String status;
    private int entryCount;
}

public class PromptLibraryEntry {
    private String id;
    private String sourceId;
    private String sourceName;
    private String sourceUrl;
    private String license;
    private String status;
    private String title;
    private String category;
    private List<String> tags = new ArrayList<String>();
    private String prompt;
}
```

`PromptLibraryLoadResult` 使用不可变构造参数表达：

```java
public PromptLibraryLoadResult(List<PromptLibrarySource> sources,
                               List<PromptLibraryEntry> entries,
                               int errorCount,
                               String message)
```

所有 JSON 模型加 `@JsonIgnoreProperties(ignoreUnknown = true)`，保证上游以后增加非业务字段时仍可向后兼容。

- [ ] **Step 4: 实现可降级加载器**

`PromptLibraryLoader` 固定使用：

```java
@Component
public class PromptLibraryLoader {
private static final String DEFAULT_RESOURCE =
        "templates/prompt-console/prompt-library.json";
private static final int EXPECTED_ENTRY_COUNT = 4409;

public PromptLibraryLoadResult loadDefault() {
    return load(new ClassPathResource(DEFAULT_RESOURCE));
}
}
```

`load(Resource)` 用 `ObjectMapper.readValue` 读取 `PromptLibraryCatalog`，保留标题和 Prompt 都有内容的条目；字段缺失条目累计 `errorCount`。资源读取异常返回空集合和中文错误信息，不向上抛出导致 Spring Boot 启动失败。真实资源数量不是 4409 时，消息中同时记录预期数和实际数。

- [ ] **Step 5: 运行加载器测试**

Run:

```powershell
mvn -pl imagetemplate -am '-Dtest=PromptLibraryLoaderTest' -DfailIfNoTests=false test
```

Expected: 3 个加载器测试 PASS。

- [ ] **Step 6: 提交大库加载器**

```powershell
git add -- imagetemplate/src/main/java/com/example/imagetemplate/model/PromptLibraryCatalog.java imagetemplate/src/main/java/com/example/imagetemplate/model/PromptLibrarySource.java imagetemplate/src/main/java/com/example/imagetemplate/model/PromptLibraryEntry.java imagetemplate/src/main/java/com/example/imagetemplate/model/PromptLibraryLoadResult.java imagetemplate/src/main/java/com/example/imagetemplate/service/PromptLibraryLoader.java imagetemplate/src/test/java/com/example/imagetemplate/service/PromptLibraryLoaderTest.java
git commit -m "feat(imagetemplate): load shared prompt catalog"
```

### Task 3: 适配大库条目并生成稳定唯一 ID

**Files:**

- Modify: `imagetemplate/src/main/java/com/example/imagetemplate/model/ImagePromptTemplate.java`
- Create: `imagetemplate/src/main/java/com/example/imagetemplate/service/ImagePromptTemplateAdapter.java`
- Create: `imagetemplate/src/test/java/com/example/imagetemplate/service/ImagePromptTemplateAdapterTest.java`

- [ ] **Step 1: 写入适配行为测试**

测试构造两个完全相同的条目和一个通用条目，断言：

```java
List<ImagePromptTemplate> adapted = adapter.adapt(Arrays.asList(imageEntry, imageEntry, textEntry));

assertThat(adapted).hasSize(3);
assertThat(adapted).extracting("id").doesNotHaveDuplicates();
assertThat(adapted.get(0).getId()).startsWith("library-youmind-awesome-gpt-image-2-");
assertThat(adapted.get(0).getTemplateKind()).isEqualTo("DIRECT");
assertThat(adapted.get(0).isImageRelated()).isTrue();
assertThat(adapted.get(0).isCurated()).isFalse();
assertThat(adapted.get(0).getJsonTemplate()).isEmpty();
assertThat(adapted.get(2).isImageRelated()).isFalse();
```

另加稳定性断言：

```java
assertThat(adapter.adapt(Collections.singletonList(imageEntry)).get(0).getId())
        .isEqualTo(adapter.adapt(Collections.singletonList(imageEntry)).get(0).getId());
```

- [ ] **Step 2: 运行测试并确认新字段和适配器缺失**

Run:

```powershell
mvn -pl imagetemplate -am '-Dtest=ImagePromptTemplateAdapterTest' -DfailIfNoTests=false test
```

Expected: FAIL，`ImagePromptTemplateAdapter` 和新增模板字段尚不存在。

- [ ] **Step 3: 扩展统一模板模型**

在 `ImagePromptTemplate` 增加 JavaBean 字段：

```java
private String sourceId;
private String sourceName;
private String templateKind;
private boolean imageRelated;
private boolean curated;
```

精选模板加载后由聚合服务补齐：

```text
sourceId=curated
sourceName=精选模板
templateKind=direct-prompt 分类时为 DIRECT，否则为 STRUCTURED
imageRelated=true
curated=true
```

- [ ] **Step 4: 实现映射、摘要、分类 slug 和稳定 ID**

`ImagePromptTemplateAdapter` 标记为 `@Component`，并使用以下规则：

```java
template.setId(uniqueId(entry, occurrence));
template.setTitle(entry.getTitle().trim());
template.setCategory(entry.getCategory().trim());
template.setCategorySlug("library-category-" + sha256(entry.getCategory()).substring(0, 12));
template.setSummary(summary(entry.getPrompt(), 180));
template.setTags(entry.getTags());
template.setJsonTemplate(new LinkedHashMap<String, Object>());
template.setPromptTemplate(entry.getPrompt());
template.setSourceUrl(entry.getSourceUrl());
template.setSourceId(entry.getSourceId());
template.setSourceName(entry.getSourceName());
template.setTemplateKind("DIRECT");
template.setImageRelated(isImageRelated(entry));
template.setCurated(false);
```

基础 ID 为：

```text
library-{规范化 sourceId}-{规范化 originalId}-{SHA-256 前 12 位}
```

完整摘要输入固定为 `sourceId + "\n" + id + "\n" + title + "\n" + category + "\n" + prompt`。完全重复时，第一个不加后缀，后续按出现顺序追加 `-2`、`-3`。

图片专用来源固定为：

```java
private static final Set<String> IMAGE_SOURCE_IDS = new HashSet<String>(Arrays.asList(
        "youmind-awesome-gpt-image-2",
        "freestylefly-awesome-gpt-image-2",
        "evolink-awesome-gpt-image-2-prompts"
));
```

其他来源对分类和标签的小写文本匹配 `图片、图像、视觉、海报、摄影、插画、logo、ui、电商、角色、image、photo、poster、illustration、visual`。

- [ ] **Step 5: 运行适配器测试**

Run:

```powershell
mvn -pl imagetemplate -am '-Dtest=ImagePromptTemplateAdapterTest' -DfailIfNoTests=false test
```

Expected: 适配、稳定 ID、重复行和图片相关判定全部 PASS。

- [ ] **Step 6: 提交统一模板适配器**

```powershell
git add -- imagetemplate/src/main/java/com/example/imagetemplate/model/ImagePromptTemplate.java imagetemplate/src/main/java/com/example/imagetemplate/service/ImagePromptTemplateAdapter.java imagetemplate/src/test/java/com/example/imagetemplate/service/ImagePromptTemplateAdapterTest.java
git commit -m "feat(imagetemplate): adapt prompt library entries"
```

### Task 4: 聚合 4456 条模板并实现分页查询

**Files:**

- Create: `imagetemplate/src/main/java/com/example/imagetemplate/model/LibraryAggregationStatus.java`
- Create: `imagetemplate/src/main/java/com/example/imagetemplate/dto/ImageTemplateQuery.java`
- Create: `imagetemplate/src/main/java/com/example/imagetemplate/dto/ImageTemplateSummaryResponse.java`
- Create: `imagetemplate/src/main/java/com/example/imagetemplate/dto/ImageTemplatePageResponse.java`
- Create: `imagetemplate/src/main/java/com/example/imagetemplate/dto/ImageTemplateMetaResponse.java`
- Create: `imagetemplate/src/main/java/com/example/imagetemplate/dto/TemplateSourceResponse.java`
- Create: `imagetemplate/src/main/java/com/example/imagetemplate/service/ImageTemplateQueryValidationException.java`
- Modify: `imagetemplate/src/main/java/com/example/imagetemplate/service/ImagePromptTemplateService.java`
- Modify: `imagetemplate/src/test/java/com/example/imagetemplate/service/ImagePromptTemplateServiceTest.java`

- [ ] **Step 1: 将服务测试改为聚合数量和唯一 ID 契约**

`setUp()` 改为显式创建依赖：

```java
ObjectMapper objectMapper = new ObjectMapper();
PromptLibraryLoader loader = new PromptLibraryLoader(objectMapper);
ImagePromptTemplateAdapter adapter = new ImagePromptTemplateAdapter();
imagePromptTemplateService = new ImagePromptTemplateService(objectMapper, loader, adapter);
```

新增核心断言：

```java
@Test
void aggregatesCuratedAndSharedLibrariesWithoutDroppingRows() {
    ImageTemplateMetaResponse meta = imagePromptTemplateService.getMeta();

    assertThat(meta.getStatus().getStatus()).isEqualTo("READY");
    assertThat(meta.getStatus().getLoadedCuratedCount()).isEqualTo(47);
    assertThat(meta.getStatus().getLoadedLibraryCount()).isEqualTo(4409);
    assertThat(meta.getTotal()).isEqualTo(4456);
    assertThat(meta.getSources()).hasSize(7);
}

@Test
void aggregateIdsAreUniqueAndCuratedTemplatesRemainFirst() {
    List<ImageTemplateSummaryResponse> templates =
            new ArrayList<ImageTemplateSummaryResponse>();
    for (int pageNumber = 1; pageNumber <= 45; pageNumber++) {
        ImageTemplateQuery query = new ImageTemplateQuery();
        query.setPage(pageNumber);
        query.setSize(100);
        templates.addAll(imagePromptTemplateService.search(query).getTemplates());
    }

    assertThat(templates).hasSize(4456);
    assertThat(templates).extracting("id").doesNotHaveDuplicates();
    assertThat(templates.subList(0, 47))
            .allMatch(ImageTemplateSummaryResponse::isCurated);
}
```

- [ ] **Step 2: 写分页、组合筛选和 DIRECT 渲染测试**

```java
@Test
void pagesAndFiltersTemplatesUsingSummaryResults() {
    ImageTemplateQuery query = new ImageTemplateQuery();
    query.setPage(1);
    query.setSize(48);
    query.setSource("youmind-awesome-gpt-image-2");
    query.setImageOnly(true);

    ImageTemplatePageResponse page = imagePromptTemplateService.search(query);

    assertThat(page.getTemplates()).hasSizeLessThanOrEqualTo(48);
    assertThat(page.getTotal()).isGreaterThan(0);
    assertThat(page.getTemplates()).allMatch(item ->
            "youmind-awesome-gpt-image-2".equals(item.getSourceId())
                    && item.isImageRelated());
}

@Test
void directTemplateReturnsOriginalPromptAndAppendsDirectorNote() {
    ImageTemplateQuery query = new ImageTemplateQuery();
    query.setSource("prompt123");
    ImagePromptTemplate template =
            imagePromptTemplateService.findById(imagePromptTemplateService.search(query)
                    .getTemplates().get(0).getId());
    PromptRenderRequest request = new PromptRenderRequest();
    request.setExtraInstruction("改成适合图像生成的构图。");

    assertThat(imagePromptTemplateService.renderPrompt(template.getId(), request))
            .startsWith(template.getPromptTemplate())
            .endsWith("用户补充要求：改成适合图像生成的构图。");
}
```

参数边界测试：

```java
ImageTemplateQuery invalidPage = new ImageTemplateQuery();
invalidPage.setPage(0);
ImageTemplateQuery invalidSize = new ImageTemplateQuery();
invalidSize.setSize(101);

assertThatThrownBy(() -> imagePromptTemplateService.search(invalidPage))
        .isInstanceOf(ImageTemplateQueryValidationException.class);
assertThatThrownBy(() -> imagePromptTemplateService.search(invalidSize))
        .isInstanceOf(ImageTemplateQueryValidationException.class);
```

降级测试通过 Mockito 固定加载失败结果：

```java
PromptLibraryLoader degradedLoader = mock(PromptLibraryLoader.class);
when(degradedLoader.loadDefault()).thenReturn(new PromptLibraryLoadResult(
        Collections.<PromptLibrarySource>emptyList(),
        Collections.<PromptLibraryEntry>emptyList(),
        1,
        "大库资源解析失败"));
ImagePromptTemplateService degradedService = new ImagePromptTemplateService(
        new ObjectMapper(), degradedLoader, new ImagePromptTemplateAdapter());

assertThat(degradedService.getMeta().getStatus().getStatus()).isEqualTo("DEGRADED");
assertThat(degradedService.getMeta().getTotal()).isEqualTo(47);
assertThat(degradedService.search(new ImageTemplateQuery()).getTemplates()).hasSize(47);
```

- [ ] **Step 3: 运行服务测试并确认旧服务不满足新契约**

Run:

```powershell
mvn -pl imagetemplate -am '-Dtest=ImagePromptTemplateServiceTest' -DfailIfNoTests=false test
```

Expected: FAIL，分页 DTO、聚合状态和新构造函数尚不存在。

- [ ] **Step 4: 实现查询和响应 DTO**

`ImageTemplateQuery` 默认值：

```java
private int page = 1;
private int size = 48;
private String keyword;
private String source;
private String category;
private boolean imageOnly;
```

`ImageTemplateSummaryResponse` 只包含：

```text
id, title, summary, category, categorySlug, tags,
sourceId, sourceName, templateKind, imageRelated, curated
```

`ImageTemplatePageResponse` 包含：

```text
success=true, total, page, size, hasMore, libraryStatus, message, templates
```

`LibraryAggregationStatus` 包含：

```text
status, expectedCuratedCount=47, loadedCuratedCount,
expectedLibraryCount=4409, loadedLibraryCount, total, message
```

`ImageTemplateMetaResponse` 包含：

```text
success=true, total, curatedCount, libraryCount, imageRelatedCount,
status, sources, categories
```

- [ ] **Step 5: 重写服务初始化和只读索引**

构造函数加载两套数据并组装：

```java
public ImagePromptTemplateService(ObjectMapper objectMapper,
                                  PromptLibraryLoader promptLibraryLoader,
                                  ImagePromptTemplateAdapter adapter) {
    List<ImagePromptTemplate> curated = loadCuratedTemplates(objectMapper);
    decorateCurated(curated);
    PromptLibraryLoadResult library = promptLibraryLoader.loadDefault();
    List<ImagePromptTemplate> imported = adapter.adapt(library.getEntries());

    List<ImagePromptTemplate> aggregated = new ArrayList<ImagePromptTemplate>();
    aggregated.addAll(curated);
    aggregated.addAll(imported);
    this.templates = Collections.unmodifiableList(aggregated);
    this.templatesById = Collections.unmodifiableMap(indexById(aggregated));
    this.status = buildStatus(curated, imported, library);
}
```

精选加载失败也进入 `DEGRADED`，但不阻止已成功的大库使用。状态仅在 47 和 4409 都完整且没有加载错误时为 `READY`。

- [ ] **Step 6: 实现组合过滤、分页、元数据和兼容分类接口**

过滤顺序固定为：

```text
source -> category -> imageOnly -> keyword
```

keyword 搜索内容为标题、摘要、分类、标签、来源名和完整 Prompt。分页先过滤、后计算 `fromIndex=(page-1)*size`，超出总数返回空页而不是异常；`page < 1`、`size < 1` 或 `size > 100` 抛 `ImageTemplateQueryValidationException`。

保留 `listCategories()`，使旧 `/categories` 接口继续工作；新增 `getMeta()` 返回所有来源和分类统计。`findById` 改用不可变 Map 索引。

- [ ] **Step 7: 分离 DIRECT 和 STRUCTURED Prompt 渲染**

DIRECT 分支：

```java
if ("DIRECT".equals(template.getTemplateKind())) {
    StringBuilder direct = new StringBuilder(template.getPromptTemplate().trim());
    if (hasText(extraInstruction)) {
        direct.append("\n\n用户补充要求：").append(extraInstruction.trim());
    }
    return direct.toString();
}
```

STRUCTURED 分支保持原有变量覆盖、结构化展开和输出限制。

- [ ] **Step 8: 运行完整服务测试**

Run:

```powershell
mvn -pl imagetemplate -am '-Dtest=ImagePromptTemplateServiceTest,PromptLibraryLoaderTest,ImagePromptTemplateAdapterTest' -DfailIfNoTests=false test
```

Expected: 聚合总数 4456、ID 唯一、分页、过滤、详情和两种渲染测试全部 PASS。

- [ ] **Step 9: 提交聚合查询服务**

```powershell
git add -- imagetemplate/src/main/java/com/example/imagetemplate/model/LibraryAggregationStatus.java imagetemplate/src/main/java/com/example/imagetemplate/dto/ImageTemplateQuery.java imagetemplate/src/main/java/com/example/imagetemplate/dto/ImageTemplateSummaryResponse.java imagetemplate/src/main/java/com/example/imagetemplate/dto/ImageTemplatePageResponse.java imagetemplate/src/main/java/com/example/imagetemplate/dto/ImageTemplateMetaResponse.java imagetemplate/src/main/java/com/example/imagetemplate/dto/TemplateSourceResponse.java imagetemplate/src/main/java/com/example/imagetemplate/service/ImageTemplateQueryValidationException.java imagetemplate/src/main/java/com/example/imagetemplate/service/ImagePromptTemplateService.java imagetemplate/src/test/java/com/example/imagetemplate/service/ImagePromptTemplateServiceTest.java
git commit -m "feat(imagetemplate): aggregate and page prompt templates"
```

### Task 5: 暴露分页列表和聚合元数据 API

**Files:**

- Modify: `imagetemplate/src/main/java/com/example/imagetemplate/controller/ImagePromptTemplateController.java`
- Create: `imagetemplate/src/test/java/com/example/imagetemplate/controller/ImagePromptTemplateControllerTest.java`

- [ ] **Step 1: 写分页摘要、元数据和错误响应测试**

使用 `MockMvcBuilders.standaloneSetup(controller)`，新增：

```java
mockMvc.perform(get("/api/image-templates")
        .param("page", "1")
        .param("size", "48")
        .param("source", "curated")
        .param("imageOnly", "true"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.success").value(true))
        .andExpect(jsonPath("$.page").value(1))
        .andExpect(jsonPath("$.size").value(48))
        .andExpect(jsonPath("$.templates[0].promptTemplate").doesNotExist())
        .andExpect(jsonPath("$.templates[0].jsonTemplate").doesNotExist());

mockMvc.perform(get("/api/image-templates/meta"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.total").value(4456))
        .andExpect(jsonPath("$.status.status").value("READY"))
        .andExpect(jsonPath("$.sources.length()").value(7));

mockMvc.perform(get("/api/image-templates").param("size", "101"))
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.success").value(false))
        .andExpect(jsonPath("$.message").value(org.hamcrest.Matchers.containsString("100")));
```

详情测试断言 `promptTemplate` 和 `jsonTemplate` 存在。

- [ ] **Step 2: 运行 Controller 测试并确认旧响应失败**

Run:

```powershell
mvn -pl imagetemplate -am '-Dtest=ImagePromptTemplateControllerTest' -DfailIfNoTests=false test
```

Expected: FAIL，旧列表不接受分页、来源和图片筛选，也没有 `/meta`。

- [ ] **Step 3: 将列表入口改为强类型分页响应**

Controller 方法签名改为：

```java
@GetMapping
public ImageTemplatePageResponse listTemplates(
        @RequestParam(value = "page", defaultValue = "1") int page,
        @RequestParam(value = "size", defaultValue = "48") int size,
        @RequestParam(value = "keyword", required = false) String keyword,
        @RequestParam(value = "source", required = false) String source,
        @RequestParam(value = "category", required = false) String category,
        @RequestParam(value = "imageOnly", defaultValue = "false") boolean imageOnly) {
    ImageTemplateQuery query = new ImageTemplateQuery();
    query.setPage(page);
    query.setSize(size);
    query.setKeyword(keyword);
    query.setSource(source);
    query.setCategory(category);
    query.setImageOnly(imageOnly);
    return imagePromptTemplateService.search(query);
}
```

- [ ] **Step 4: 增加元数据和稳定参数错误**

```java
@GetMapping("/meta")
public ImageTemplateMetaResponse getMeta() {
    return imagePromptTemplateService.getMeta();
}

@ExceptionHandler(ImageTemplateQueryValidationException.class)
@ResponseStatus(HttpStatus.BAD_REQUEST)
public Map<String, Object> handleQueryValidation(
        ImageTemplateQueryValidationException exception) {
    Map<String, Object> result = new LinkedHashMap<String, Object>();
    result.put("success", false);
    result.put("message", exception.getMessage());
    return result;
}
```

确保 `/meta` 和 `/categories` 在 `/{id}` 前由 Spring MVC 正确匹配。

- [ ] **Step 5: 运行 Controller 和服务测试**

Run:

```powershell
mvn -pl imagetemplate -am '-Dtest=ImagePromptTemplateControllerTest,ImagePromptTemplateServiceTest' -DfailIfNoTests=false test
```

Expected: Controller 摘要隔离、元数据、详情和 HTTP 400 测试全部 PASS。

- [ ] **Step 6: 提交分页 API**

```powershell
git add -- imagetemplate/src/main/java/com/example/imagetemplate/controller/ImagePromptTemplateController.java imagetemplate/src/test/java/com/example/imagetemplate/controller/ImagePromptTemplateControllerTest.java
git commit -m "feat(imagetemplate): expose paged template API"
```

### Task 6: 增加聚合模板库前端控件

**Files:**

- Modify: `imagetemplate/src/test/java/com/example/imagetemplate/ImageTemplateHomepageStaticAssetsTest.java`
- Modify: `imagetemplate/src/main/resources/static/index.html`
- Modify: `imagetemplate/src/main/resources/static/css/app.css`

- [ ] **Step 1: 写新控件静态契约**

在现有控件数组中移除 `categoryTabs`，并加入：

```java
"libraryAlert", "sourceFilters", "categorySelect", "imageOnlyToggle",
"loadMoreButton", "listStatus"
```

JavaScript/CSS 静态断言加入：

```java
assertThat(js)
        .contains("SEARCH_DEBOUNCE_MS = 300")
        .contains("loadMeta")
        .contains("loadTemplatePage")
        .contains("loadTemplateDetail")
        .contains("resetPagination");
assertThat(css)
        .contains(".library-alert")
        .contains(".source-filters")
        .contains(".template-badge")
        .contains(".load-more");
```

- [ ] **Step 2: 运行静态测试并确认控件缺失**

Run:

```powershell
mvn -pl imagetemplate -am '-Dtest=ImageTemplateHomepageStaticAssetsTest' -DfailIfNoTests=false test
```

Expected: FAIL，新控件和脚本函数尚不存在。

- [ ] **Step 3: 改造灵感大厅筛选区**

保留 `keywordInput` 和 `templateList`，把原 `categoryTabs` 节点替换为：

```html
<div id="libraryAlert" class="library-alert" role="alert" hidden></div>
<div id="sourceFilters" class="source-filters" aria-label="提示词来源"></div>
<div class="library-filters">
    <label for="categorySelect">
        <span>分类</span>
        <select id="categorySelect">
            <option value="">全部分类</option>
        </select>
    </label>
    <label class="image-only-control" for="imageOnlyToggle">
        <input id="imageOnlyToggle" type="checkbox">
        <span>仅图片相关</span>
    </label>
</div>
<div id="listStatus" class="list-status" role="status"></div>
<div class="template-list" id="templateList" aria-live="polite"></div>
<button id="loadMoreButton" class="load-more" type="button" hidden>加载更多</button>
```

更新首屏说明为“精选图片模板与 6 个公开提示词来源汇聚于此”，使页面文案不再暗示只有图片专用模板。

- [ ] **Step 4: 添加聚合控件和移动端样式**

样式要求：

```text
library-alert：DEGRADED 时使用暖红边框和半透明暗底；
source-filters：桌面横向排列，溢出可滚动；
library-filters：分类下拉与图片开关同行；
template-badge：区分“精选”“来源名”“通用提示词”；
load-more：最小点击高度 44px，居中且沿用黑金边框；
390px：筛选器纵向排列，来源仍可横向滑动，页面无横向溢出。
```

- [ ] **Step 5: 运行静态测试**

Run:

```powershell
mvn -pl imagetemplate -am '-Dtest=ImageTemplateHomepageStaticAssetsTest' -DfailIfNoTests=false test
```

Expected: HTML 控件和 CSS 契约 PASS；JavaScript 行为断言仍在下一任务完成。

- [ ] **Step 6: 提交前端结构与样式**

```powershell
git add -- imagetemplate/src/test/java/com/example/imagetemplate/ImageTemplateHomepageStaticAssetsTest.java imagetemplate/src/main/resources/static/index.html imagetemplate/src/main/resources/static/css/app.css
git commit -m "feat(imagetemplate): add aggregate library controls"
```

### Task 7: 实现分页、搜索防抖和详情按需加载

**Files:**

- Modify: `imagetemplate/src/main/resources/static/js/app.js`
- Modify: `imagetemplate/src/test/java/com/example/imagetemplate/ImageTemplateHomepageStaticAssetsTest.java`

- [ ] **Step 1: 建立前端分页状态**

将状态扩展为：

```javascript
var state = {
    activeSource: '',
    activeCategory: '',
    keyword: '',
    imageOnly: false,
    page: 1,
    size: 48,
    total: 0,
    hasMore: false,
    templates: [],
    sources: [],
    categories: [],
    libraryStatus: null,
    selected: null,
    renderedPromptEdited: false,
    referenceImages: []
};
var SEARCH_DEBOUNCE_MS = 300;
var searchTimer = null;
var listRequestSequence = 0;
```

elements 新增 `libraryAlert`、`sourceFilters`、`categorySelect`、`imageOnlyToggle`、`loadMoreButton` 和 `listStatus`。

- [ ] **Step 2: 用元数据入口替代分类入口**

实现：

```javascript
function loadMeta() {
    return fetchJson('/api/image-templates/meta').then(function (payload) {
        state.sources = payload.sources || [];
        state.categories = payload.categories || [];
        state.libraryStatus = payload.status || null;
        state.total = payload.total || 0;
        renderMeta();
    });
}
```

`renderMeta()`：

- 渲染“全部”和 7 个来源按钮；
- 渲染分类 `<option>`；
- `status.status === 'DEGRADED'` 时显示预期数量、实际数量和 message；
- READY 时隐藏 `libraryAlert`。

- [ ] **Step 3: 实现分页请求、竞态保护和加载更多**

```javascript
function loadTemplatePage(append) {
    var requestSequence = ++listRequestSequence;
    var params = new URLSearchParams();
    params.set('page', String(state.page));
    params.set('size', String(state.size));
    if (state.activeSource) {
        params.set('source', state.activeSource);
    }
    if (state.activeCategory) {
        params.set('category', state.activeCategory);
    }
    if (state.keyword) {
        params.set('keyword', state.keyword);
    }
    if (state.imageOnly) {
        params.set('imageOnly', 'true');
    }
    elements.listStatus.textContent = append ? '正在加载更多模板…' : '正在检索模板…';
    return fetchJson('/api/image-templates?' + params.toString()).then(function (payload) {
        if (requestSequence !== listRequestSequence) {
            return;
        }
        var incoming = payload.templates || [];
        state.templates = append ? state.templates.concat(incoming) : incoming;
        state.total = payload.total || 0;
        state.hasMore = Boolean(payload.hasMore);
        elements.templateCount.textContent = String(state.total);
        elements.listStatus.textContent =
                '已展示 ' + state.templates.length + ' / ' + state.total + ' 条';
        elements.loadMoreButton.hidden = !state.hasMore;
        renderTemplates();
    });
}

function resetPagination() {
    state.page = 1;
    state.templates = [];
    return loadTemplatePage(false);
}
```

加载更多点击时执行 `state.page += 1` 和 `loadTemplatePage(true)`；失败时页码回退并保留已有卡片。

- [ ] **Step 4: 将卡片选择改为详情按需加载**

摘要卡片只保存列表字段。实现：

```javascript
function loadTemplateDetail(id) {
    elements.statusLine.textContent = '正在读取完整模板…';
    return fetchJson('/api/image-templates/' + encodeURIComponent(id))
        .then(function (payload) {
            state.selected = payload.template || null;
            renderTemplates();
            renderDetail();
        })
        .catch(function () {
            elements.statusLine.textContent = '模板详情加载失败，请重试。';
        });
}
```

失败时不得把 `state.selected`、`renderedPrompt` 或生成参数清空。

- [ ] **Step 5: 适配 DIRECT 和 STRUCTURED 编辑界面**

`renderDetail()` 依据 `template.templateKind`：

```javascript
var direct = template.templateKind === 'DIRECT';
elements.variablesInput.disabled = direct;
elements.variablesInput.value = direct ? '{}' : buildVariableSeed(template.jsonTemplate);
elements.renderedPrompt.value = direct ? (template.promptTemplate || '') : '';
```

DIRECT 显示“直接提示词”；`imageRelated === false` 显示“通用提示词，请先调整为适合图片生成的描述”，但不禁用 Prompt 或生成按钮。

- [ ] **Step 6: 接入筛选事件和 300ms 防抖**

```javascript
elements.keywordInput.addEventListener('input', function () {
    state.keyword = elements.keywordInput.value.trim();
    window.clearTimeout(searchTimer);
    searchTimer = window.setTimeout(resetPagination, SEARCH_DEBOUNCE_MS);
});
```

来源按钮、分类下拉和图片开关变更时更新 state 并立即 `resetPagination()`。首次启动：

```javascript
loadMeta()
    .then(function () { return loadTemplatePage(false); })
    .catch(function (error) {
        elements.libraryAlert.hidden = false;
        elements.libraryAlert.textContent = error.message || '模板库加载失败。';
    });
```

- [ ] **Step 7: 运行静态和后端回归**

Run:

```powershell
mvn -pl imagetemplate -am test
```

Expected: 静态契约、服务、Controller、健康检查和 OpenAI 参数测试全部 PASS。

- [ ] **Step 8: 提交前端聚合交互**

```powershell
git add -- imagetemplate/src/main/resources/static/js/app.js imagetemplate/src/test/java/com/example/imagetemplate/ImageTemplateHomepageStaticAssetsTest.java
git commit -m "feat(imagetemplate): browse full paged prompt library"
```

### Task 8: 同步项目文档

**Files:**

- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `imagetemplate/README.md`
- Modify: `imagetemplate/AGENTS.md`

- [ ] **Step 1: 更新数量、来源和职责**

四份文档统一说明：

```text
imagetemplate 聚合 47 条精选图片模板和 Prompt Console 的 4409 条提示词，
总计 4456 条；website/src/main/resources/static/prompt-console/data/prompt-library.json
是大库唯一源码，
Maven 构建时复制到 imagetemplate classpath，运行时不依赖 website 服务。
```

把“47 个模板是唯一数据源”改为“两套 classpath 资源在运行时聚合”，同时保留 47 个精选模板的维护说明。

- [ ] **Step 2: 更新 API 和前端行为**

文档 API 列表加入：

```text
GET /api/image-templates?page=1&size=48&keyword=&source=&category=&imageOnly=false
GET /api/image-templates/meta
```

说明列表默认 48、最大 100，只返回摘要；详情返回完整 Prompt；前端使用来源、分类、图片相关筛选、300ms 防抖和加载更多。

- [ ] **Step 3: 更新测试和打包验证命令**

加入：

```powershell
mvn -pl imagetemplate -am test
mvn -pl imagetemplate -am clean package -DskipTests
jar tf imagetemplate/target/imagetemplate-0.0.1-SNAPSHOT.jar | Select-String "templates/prompt-console/prompt-library.json"
```

说明聚合状态为 `DEGRADED` 时页面必须显示预期数量、实际数量和错误信息。

- [ ] **Step 4: 检查旧数量和唯一数据源表述**

Run:

```powershell
rg -n "47 个模板|47个模板|唯一数据源|/api/image-templates" README.md AGENTS.md imagetemplate/README.md imagetemplate/AGENTS.md
```

Expected: 仍出现的 47 仅指精选库；API 表述包含分页和 `/meta`；不存在“大库只有 47 条”的旧描述。

- [ ] **Step 5: 提交文档**

```powershell
git add -- README.md AGENTS.md imagetemplate/README.md imagetemplate/AGENTS.md
git commit -m "docs(imagetemplate): document full library aggregation"
```

### Task 9: 完成打包、API 和浏览器验收

**Files:**

- Verify: `imagetemplate/target/imagetemplate-0.0.1-SNAPSHOT.jar`
- Verify: `imagetemplate/src/main/resources/static/index.html`

- [ ] **Step 1: 运行完整模块测试**

Run:

```powershell
mvn -pl imagetemplate -am clean test
```

Expected: Maven `BUILD SUCCESS`，所有 imagetemplate 测试通过。

- [ ] **Step 2: 打包并验证 jar 内含大库**

Run:

```powershell
mvn -pl imagetemplate -am clean package -DskipTests
jar tf imagetemplate/target/imagetemplate-0.0.1-SNAPSHOT.jar | Select-String "templates/prompt-console/prompt-library.json"
```

Expected: Maven `BUILD SUCCESS`，jar 清单包含 `BOOT-INF/classes/templates/prompt-console/prompt-library.json`。

- [ ] **Step 3: 启动服务并验证聚合 API**

Run:

```powershell
mvn -pl imagetemplate -am spring-boot:run
```

另一个终端执行：

```powershell
$meta = Invoke-RestMethod http://127.0.0.1:8082/api/image-templates/meta
$page = Invoke-RestMethod 'http://127.0.0.1:8082/api/image-templates?page=1&size=48'
$meta.total
$meta.status.status
$page.templates.Count
$page.templates[0].PSObject.Properties.Name
```

Expected:

```text
4456
READY
48
```

列表条目字段中没有 `promptTemplate` 和 `jsonTemplate`。

- [ ] **Step 4: 验证过滤、末端记录和详情**

Run:

```powershell
$filtered = Invoke-RestMethod 'http://127.0.0.1:8082/api/image-templates?page=1&size=100&source=youmind-awesome-gpt-image-2&imageOnly=true'
$search = Invoke-RestMethod 'http://127.0.0.1:8082/api/image-templates?page=1&size=48&keyword=%E5%B0%8F%E7%BA%A2%E4%B9%A6%E7%88%86%E6%AC%BE%E4%BD%9C%E5%93%81%E5%8F%91%E5%B8%83%E6%97%B6%E9%97%B4'
$detail = Invoke-RestMethod ('http://127.0.0.1:8082/api/image-templates/' + $search.templates[0].id)
$filtered.templates.Count
$detail.template.promptTemplate.Length
```

Expected: 图片来源过滤结果非空；搜索可找到大库记录；详情 Prompt 长度大于摘要长度。

- [ ] **Step 5: 浏览器检查桌面和 390px 移动端**

访问 `http://127.0.0.1:8082/` 并确认：

```text
默认总数 4456；
首屏 48 张卡片；
加载更多后无重复；
来源、分类、仅图片相关和关键词组合筛选可用；
精选 STRUCTURED 模板显示变量 JSON；
大库 DIRECT 模板禁用变量 JSON 并直接填充 Prompt；
通用提示词显示提醒但仍可生成；
390px 下没有页面级横向溢出；
四场景 Dock、减少动态效果和现有生成参数保持可用。
```

- [ ] **Step 6: 检查工作区和提交历史**

Run:

```powershell
git status --short
git log --oneline -10
git diff master~8..master --check
```

Expected: 本任务涉及的文件均已提交；仅保留任务开始前已有的无关未跟踪文件；diff 无空白错误。
