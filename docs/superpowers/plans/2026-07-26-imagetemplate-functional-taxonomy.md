# Imagetemplate Functional Taxonomy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace source-first template browsing with a deterministic “一级功能 + 二级场景” taxonomy for all 4456 aggregated templates while preserving source and legacy category compatibility.

**Architecture:** A focused `TemplateFunctionClassifier` assigns one immutable functional classification from template ID, title, original category, tags, and low-priority source defaults. The aggregate service decorates templates once at startup, builds hierarchical counts, and supports functional filters; the browser renders first-level and second-level navigation while moving source and original-category controls into a collapsed advanced filter.

**Tech Stack:** Java 8, Spring Boot 2.6.13, Jackson, JUnit 5, AssertJ, Spring MockMvc, vanilla HTML/CSS/JavaScript, Maven.

---

### Task 1: Define the taxonomy catalog and deterministic classifier

**Files:**
- Create: `imagetemplate/src/main/java/com/example/imagetemplate/model/TemplateFunctionClassification.java`
- Create: `imagetemplate/src/main/java/com/example/imagetemplate/service/TemplateFunctionClassifier.java`
- Test: `imagetemplate/src/test/java/com/example/imagetemplate/service/TemplateFunctionClassifierTest.java`

- [ ] **Step 1: Write classifier tests that describe the catalog and precedence**

Create tests that assert:

```java
@Test
void exposesFifteenOrderedCategoriesWithProgrammingVisible() {
    assertThat(classifier.getCatalog()).hasSize(15);
    assertThat(classifier.getCatalog())
            .extracting("slug")
            .contains("programming-development");
}

@Test
void classifiesProgrammingScenariosFromHighConfidenceTitles() {
    assertClassification("Python 自动化脚本生成器", "文本",
            Arrays.asList("编程"), "programming-development", "data-automation");
    assertClassification("Java Bug 调试专家", "角色提示",
            Arrays.asList("专业角色"), "programming-development", "debugging");
    assertClassification("React 前端页面开发助手", "文本",
            Arrays.asList("UI"), "programming-development", "frontend-development");
    assertClassification("SQL 数据库设计助手", "技术与编程",
            Arrays.asList("数据库"), "programming-development", "api-database");
}

@Test
void titleRuleWinsOverGenericTagsAndUnknownTemplatesUseFallback() {
    assertClassification("Spring 后端接口开发", "文本",
            Arrays.asList("写作", "商业"), "programming-development", "backend-development");
    assertClassification("没有可识别用途", "未知",
            Collections.<String>emptyList(), "other-tools", "general-prompt");
}
```

Also verify every category slug and every scene slug is non-empty and unique within its level.

- [ ] **Step 2: Run the focused test and verify the red state**

Run:

```powershell
mvn -pl imagetemplate -am '-Dtest=TemplateFunctionClassifierTest' -DfailIfNoTests=false test
```

Expected: test compilation fails because the classifier and classification model do not exist.

- [ ] **Step 3: Implement immutable classification values and the full catalog**

`TemplateFunctionClassification` contains:

```java
private final String categoryName;
private final String categorySlug;
private final String sceneName;
private final String sceneSlug;
```

`TemplateFunctionClassifier` exposes an ordered, immutable 15-category catalog and:

```java
public TemplateFunctionClassification classify(ImagePromptTemplate template)
```

Implement the exact catalog approved in the design spec. Rules must inspect only template ID, title, original category, tags, and source ID. Apply this precedence:

1. exact ID override;
2. high-confidence title rules;
3. original category and tag rules;
4. general title rules;
5. low-priority image-source defaults;
6. `其他工具 / 通用提示词`.

Use normalized lowercase text and ordered keyword groups. Put specific programming rules before generic writing, role, UI, or business rules. Do not inspect `promptTemplate`.

- [ ] **Step 4: Run the focused classifier tests**

Run:

```powershell
mvn -pl imagetemplate -am '-Dtest=TemplateFunctionClassifierTest' -DfailIfNoTests=false test
```

Expected: all classifier tests pass.

- [ ] **Step 5: Commit the classifier**

```powershell
git add -- imagetemplate/src/main/java/com/example/imagetemplate/model/TemplateFunctionClassification.java imagetemplate/src/main/java/com/example/imagetemplate/service/TemplateFunctionClassifier.java imagetemplate/src/test/java/com/example/imagetemplate/service/TemplateFunctionClassifierTest.java
git commit -m "feat(imagetemplate): classify templates by function"
```

### Task 2: Decorate every aggregate template and build functional metadata

**Files:**
- Modify: `imagetemplate/src/main/java/com/example/imagetemplate/model/ImagePromptTemplate.java`
- Create: `imagetemplate/src/main/java/com/example/imagetemplate/dto/TemplateFunctionCategoryResponse.java`
- Create: `imagetemplate/src/main/java/com/example/imagetemplate/dto/TemplateFunctionSceneResponse.java`
- Modify: `imagetemplate/src/main/java/com/example/imagetemplate/dto/ImageTemplateMetaResponse.java`
- Modify: `imagetemplate/src/main/java/com/example/imagetemplate/service/ImagePromptTemplateService.java`
- Test: `imagetemplate/src/test/java/com/example/imagetemplate/service/ImagePromptTemplateServiceTest.java`

- [ ] **Step 1: Add failing aggregate coverage**

Add tests that:

```java
assertThat(imagePromptTemplateService.listTemplates(null, null))
        .hasSize(4456)
        .allSatisfy(template -> {
            assertThat(template.getFunctionCategory()).isNotBlank();
            assertThat(template.getFunctionCategorySlug()).isNotBlank();
            assertThat(template.getFunctionScene()).isNotBlank();
            assertThat(template.getFunctionSceneSlug()).isNotBlank();
        });
```

Sum all `functionCategories[].count` and assert it equals 4456. Find `programming-development` and assert it has non-zero count, non-empty scenes, and a scene count sum equal to its category count.

- [ ] **Step 2: Run the service test and verify it fails**

Run:

```powershell
mvn -pl imagetemplate -am '-Dtest=ImagePromptTemplateServiceTest' -DfailIfNoTests=false test
```

Expected: compilation fails because functional fields and metadata do not exist.

- [ ] **Step 3: Add template fields and hierarchical response DTOs**

Add four bean properties to `ImagePromptTemplate`:

```java
private String functionCategory;
private String functionCategorySlug;
private String functionScene;
private String functionSceneSlug;
```

Create scene response fields `name`, `slug`, and `count`. Create category response fields `name`, `slug`, `count`, and ordered `scenes`. Add:

```java
private List<TemplateFunctionCategoryResponse> functionCategories;
```

to `ImageTemplateMetaResponse`.

- [ ] **Step 4: Classify once during aggregate construction**

Inject `TemplateFunctionClassifier` into `ImagePromptTemplateService`. Immediately after curated and imported lists are combined, classify every template and copy the four classification values onto the model before building immutable indexes.

Build functional metadata from classifier catalog order rather than first-seen template order. Include categories with zero templates so the navigation remains stable; within each category, include all declared scenes and accurate counts.

- [ ] **Step 5: Run aggregate tests**

Run:

```powershell
mvn -pl imagetemplate -am '-Dtest=TemplateFunctionClassifierTest,ImagePromptTemplateServiceTest' -DfailIfNoTests=false test
```

Expected: all focused tests pass and totals remain 4456.

- [ ] **Step 6: Commit aggregate decoration**

```powershell
git add -- imagetemplate/src/main/java/com/example/imagetemplate/model/ImagePromptTemplate.java imagetemplate/src/main/java/com/example/imagetemplate/dto/TemplateFunctionCategoryResponse.java imagetemplate/src/main/java/com/example/imagetemplate/dto/TemplateFunctionSceneResponse.java imagetemplate/src/main/java/com/example/imagetemplate/dto/ImageTemplateMetaResponse.java imagetemplate/src/main/java/com/example/imagetemplate/service/ImagePromptTemplateService.java imagetemplate/src/test/java/com/example/imagetemplate/service/ImagePromptTemplateServiceTest.java
git commit -m "feat(imagetemplate): expose functional taxonomy metadata"
```

### Task 3: Add functional query parameters without breaking legacy filters

**Files:**
- Modify: `imagetemplate/src/main/java/com/example/imagetemplate/dto/ImageTemplateQuery.java`
- Modify: `imagetemplate/src/main/java/com/example/imagetemplate/dto/ImageTemplateSummaryResponse.java`
- Modify: `imagetemplate/src/main/java/com/example/imagetemplate/controller/ImagePromptTemplateController.java`
- Modify: `imagetemplate/src/main/java/com/example/imagetemplate/service/ImagePromptTemplateService.java`
- Test: `imagetemplate/src/test/java/com/example/imagetemplate/controller/ImagePromptTemplateControllerTest.java`
- Test: `imagetemplate/src/test/java/com/example/imagetemplate/service/ImagePromptTemplateServiceTest.java`

- [ ] **Step 1: Write failing filter and API tests**

Exercise:

```text
GET /api/image-templates?functionCategory=programming-development
GET /api/image-templates?functionCategory=programming-development&functionScene=debugging
GET /api/image-templates?functionScene=debugging
GET /api/image-templates?source=prompt123&category=library-category-...
```

Assert every returned summary matches the requested functional slug, functional fields appear in JSON, `/meta` contains 15 functional categories, and legacy source/category filtering still works.

- [ ] **Step 2: Run focused tests and verify failure**

Run:

```powershell
mvn -pl imagetemplate -am '-Dtest=ImagePromptTemplateServiceTest,ImagePromptTemplateControllerTest' -DfailIfNoTests=false test
```

Expected: new functional query assertions fail.

- [ ] **Step 3: Implement query and summary fields**

Add `functionCategory` and `functionScene` to `ImageTemplateQuery`, pass both optional request parameters from the Controller, and copy all four functional properties in `ImageTemplateSummaryResponse.from(template)`.

In `search`, normalize both query values and apply:

```java
matchesFunctionCategory(template, normalizedFunctionCategory)
        && matchesFunctionScene(template, normalizedFunctionScene)
```

An omitted value or `all` matches everything. A scene-only query matches that scene slug across all categories. Existing source, original category, keyword, pagination, and image-only logic remains unchanged.

- [ ] **Step 4: Run focused API tests**

Run:

```powershell
mvn -pl imagetemplate -am '-Dtest=ImagePromptTemplateServiceTest,ImagePromptTemplateControllerTest' -DfailIfNoTests=false test
```

Expected: all focused tests pass.

- [ ] **Step 5: Commit API support**

```powershell
git add -- imagetemplate/src/main/java/com/example/imagetemplate/dto/ImageTemplateQuery.java imagetemplate/src/main/java/com/example/imagetemplate/dto/ImageTemplateSummaryResponse.java imagetemplate/src/main/java/com/example/imagetemplate/controller/ImagePromptTemplateController.java imagetemplate/src/main/java/com/example/imagetemplate/service/ImagePromptTemplateService.java imagetemplate/src/test/java/com/example/imagetemplate/controller/ImagePromptTemplateControllerTest.java imagetemplate/src/test/java/com/example/imagetemplate/service/ImagePromptTemplateServiceTest.java
git commit -m "feat(imagetemplate): filter templates by function"
```

### Task 4: Replace source-first controls with two-level functional navigation

**Files:**
- Modify: `imagetemplate/src/main/resources/static/index.html`
- Modify: `imagetemplate/src/main/resources/static/css/app.css`
- Modify: `imagetemplate/src/test/java/com/example/imagetemplate/ImageTemplateHomepageStaticAssetsTest.java`

- [ ] **Step 1: Update the static contract test first**

Require these HTML IDs:

```text
functionCategoryFilters
functionSceneFilters
advancedFilters
sourceFilters
categorySelect
```

Assert `advancedFilters` is a collapsed `<details>` element containing `sourceFilters` and `categorySelect`. Require CSS selectors for `.function-filters`, `.function-scenes`, and `.advanced-filters`.

- [ ] **Step 2: Run the static test and verify it fails**

Run:

```powershell
mvn -pl imagetemplate -am '-Dtest=ImageTemplateHomepageStaticAssetsTest' -DfailIfNoTests=false test
```

Expected: missing functional navigation elements.

- [ ] **Step 3: Implement accessible HTML controls**

Replace the visible source button row with:

```html
<div id="functionCategoryFilters" class="function-filters"
     aria-label="一级功能分类"></div>
<div id="functionSceneFilters" class="function-scenes"
     aria-label="二级功能场景"></div>
```

Move source buttons and the original category select inside:

```html
<details id="advancedFilters" class="advanced-filters">
  <summary>高级筛选</summary>
  <!-- sourceFilters and categorySelect -->
</details>
```

Keep keyword and image-only controls visible.

- [ ] **Step 4: Style desktop and mobile navigation**

Use the existing black-gold visual language. Functional category buttons must have clear active state. Secondary scenes use a quieter compact chip style. On narrow viewports, each navigation container uses local horizontal scrolling with `overflow-x: auto`; no fixed width may expand the page.

- [ ] **Step 5: Run the static test**

Run:

```powershell
mvn -pl imagetemplate -am '-Dtest=ImageTemplateHomepageStaticAssetsTest' -DfailIfNoTests=false test
```

Expected: static asset tests pass.

- [ ] **Step 6: Commit the new controls**

```powershell
git add -- imagetemplate/src/main/resources/static/index.html imagetemplate/src/main/resources/static/css/app.css imagetemplate/src/test/java/com/example/imagetemplate/ImageTemplateHomepageStaticAssetsTest.java
git commit -m "feat(imagetemplate): add functional category navigation"
```

### Task 5: Wire functional navigation into browser state and pagination

**Files:**
- Modify: `imagetemplate/src/main/resources/static/js/app.js`
- Modify: `imagetemplate/src/main/resources/static/css/app.css`
- Modify: `imagetemplate/src/test/java/com/example/imagetemplate/ImageTemplateHomepageStaticAssetsTest.java`

- [ ] **Step 1: Add failing JavaScript contract assertions**

Require the script to contain:

```text
functionCategories
activeFunctionCategory
activeFunctionScene
functionCategory
functionScene
data-function-category
data-function-scene
```

Also assert the clear-filter path resets both new state values.

- [ ] **Step 2: Run the static test and verify failure**

Run:

```powershell
mvn -pl imagetemplate -am '-Dtest=ImageTemplateHomepageStaticAssetsTest' -DfailIfNoTests=false test
```

Expected: functional browser state assertions fail.

- [ ] **Step 3: Implement metadata and request state**

Store:

```javascript
functionCategories: [],
activeFunctionCategory: '',
activeFunctionScene: ''
```

Load `payload.functionCategories`, render “全部功能” plus ordered categories, and render only the selected category’s scenes. Add `functionCategory` and `functionScene` to list query parameters when selected.

- [ ] **Step 4: Implement interactions and reset behavior**

Clicking a first-level category:

- updates `activeFunctionCategory`;
- clears `activeFunctionScene`;
- rerenders both levels;
- resets pagination and reloads results.

Clicking a scene updates `activeFunctionScene` and reloads. “清除筛选” resets both function values, source, original category, keyword, and image-only state. Source buttons continue working inside advanced filters.

- [ ] **Step 5: Prioritize functional labels on cards and detail**

Render card and detail metadata as:

```javascript
template.functionCategory + ' · ' + template.functionScene
```

Keep `sourceName` as secondary provenance text. Update empty-result copy to mention functionality, scene, and keyword.

- [ ] **Step 6: Run the static test**

Run:

```powershell
mvn -pl imagetemplate -am '-Dtest=ImageTemplateHomepageStaticAssetsTest' -DfailIfNoTests=false test
```

Expected: static tests pass.

- [ ] **Step 7: Commit browser behavior**

```powershell
git add -- imagetemplate/src/main/resources/static/js/app.js imagetemplate/src/main/resources/static/css/app.css imagetemplate/src/test/java/com/example/imagetemplate/ImageTemplateHomepageStaticAssetsTest.java
git commit -m "feat(imagetemplate): browse templates by function"
```

### Task 6: Synchronize project documentation

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `imagetemplate/README.md`
- Modify: `imagetemplate/AGENTS.md`

- [ ] **Step 1: Document user-visible and API changes**

Update all required documentation to state:

- the primary navigation is 15 first-level functions plus second-level scenes;
- “编程与技术开发” is a first-level category;
- source and raw category filters live under advanced filters;
- list query parameters include `functionCategory` and `functionScene`;
- `/meta` includes hierarchical `functionCategories`;
- classification rules live in `TemplateFunctionClassifier`;
- each template receives one deterministic primary category and scene;
- full Prompt text is not inspected for classification.

- [ ] **Step 2: Check documentation consistency**

Run:

```powershell
rg -n "functionCategory|functionScene|编程与技术开发|高级筛选|TemplateFunctionClassifier" README.md AGENTS.md imagetemplate/README.md imagetemplate/AGENTS.md
git diff --check
```

Expected: every required document mentions the new contract and `git diff --check` prints nothing.

- [ ] **Step 3: Commit documentation**

```powershell
git add -- README.md AGENTS.md imagetemplate/README.md imagetemplate/AGENTS.md
git commit -m "docs(imagetemplate): document functional taxonomy"
```

### Task 7: Run full regression, package, and browser acceptance

**Files:**
- Verify only.

- [ ] **Step 1: Run the complete module build**

Run:

```powershell
mvn -pl imagetemplate -am clean package
```

Expected: `BUILD SUCCESS`, zero test failures, and the aggregated prompt library is included in the repackaged JAR.

- [ ] **Step 2: Verify the packaged API**

Start the packaged JAR on an unused local port and verify:

```text
GET /api/image-templates/meta
GET /api/image-templates?functionCategory=programming-development
GET /api/image-templates?functionCategory=programming-development&functionScene=debugging
GET /api/image-templates?source=prompt123
```

Expected: total remains 4456, metadata exposes 15 functional categories, programming and debugging return non-zero results, and legacy source filtering still returns results.

- [ ] **Step 3: Verify desktop browser behavior**

At 1440×900 confirm:

- first-level functional navigation is visible;
- source controls are hidden until “高级筛选” is opened;
- selecting “编程与技术开发” renders its second-level scenes;
- selecting “Bug 排查与调试” updates the list;
- cards show functional category and scene;
- load-more and template detail still work;
- console and network panels contain no errors.

- [ ] **Step 4: Verify mobile behavior**

At 390×844 confirm both functional rows scroll locally, the document width does not exceed the viewport, advanced filters open correctly, and the service Dock remains usable.

- [ ] **Step 5: Perform final Git checks**

Run:

```powershell
git diff --check
git status --short
git branch --show-current
git log --oneline -12
```

Expected: branch is `master`, no task-related tracked changes remain, and unrelated pre-existing untracked files are untouched.
