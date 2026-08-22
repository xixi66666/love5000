# Guitar 吉他社曲谱本地导入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `guitar` 模块内抓取最多 50 份已授权的吉他社中文流行吉他谱，将实际 PDF/谱图保存到本地并作为 `PUBLISHED` 曲谱展示。

**Architecture:** 使用 Jsoup 实现单一来源客户端和纯解析器，以独立导入服务协调下载、魔数校验、SHA-256 去重、原子落盘及事务入库。现有普通用户 OSS 上传流程保持不变；本地导入文件使用带 `local/` 前缀的对象键，由组合 URL 服务路由到受控下载 Controller。

**Tech Stack:** Java 8、Spring Boot 2.6.13、Spring MVC、MyBatis XML、MySQL/H2、Jsoup、JUnit 5、Mockito、AssertJ

---

## 文件结构

新增文件按职责拆分：

- `guitar/src/main/java/com/example/guitar/crawler/config/GuitarCrawlerProperties.java`：绑定并校验抓取配置。
- `guitar/src/main/java/com/example/guitar/crawler/jitashe/JitasheSourceClient.java`：限速获取 HTML 和二进制文件。
- `guitar/src/main/java/com/example/guitar/crawler/jitashe/JitasheParser.java`：纯 HTML 解析，不执行网络或数据库操作。
- `guitar/src/main/java/com/example/guitar/crawler/model/SourceSheetCandidate.java`：来源候选曲谱。
- `guitar/src/main/java/com/example/guitar/crawler/model/DownloadedSheetFile.java`：已校验下载文件。
- `guitar/src/main/java/com/example/guitar/crawler/storage/LocalSheetStorage.java`：临时写入、原子提交、回滚和安全读取。
- `guitar/src/main/java/com/example/guitar/crawler/model/GuitarSheetSource.java`：来源持久化模型。
- `guitar/src/main/java/com/example/guitar/crawler/dao/GuitarSheetSourceDao.java`：来源 DAO。
- `guitar/src/main/resources/mapper/crawler/GuitarSheetSourceMapper.xml`：来源 SQL。
- `guitar/src/main/java/com/example/guitar/crawler/service/SheetImportPersistenceService.java`：曲谱、文件和来源的单事务写入。
- `guitar/src/main/java/com/example/guitar/crawler/service/JitasheSheetImportService.java`：整批导入编排。
- `guitar/src/main/java/com/example/guitar/crawler/JitasheCrawlerCommandRunner.java`：显式启用时触发一次导入。
- `guitar/src/main/java/com/example/guitar/sheet/service/RoutingSheetFileUrlService.java`：OSS 与本地对象键路由。
- `guitar/src/main/java/com/example/guitar/sheet/controller/LocalSheetFileController.java`：安全返回本地文件。

现有 `PublicOssSheetFileUrlService` 改为非默认实现；普通 OSS 上传、替换和清理类不修改业务行为。

### Task 1: 配置、依赖与数据库来源表

**Files:**
- Modify: `guitar/pom.xml`
- Modify: `guitar/src/main/resources/application.yml`
- Modify: `guitar/src/main/resources/db/guitar-schema.sql`
- Create: `guitar/src/main/java/com/example/guitar/crawler/config/GuitarCrawlerProperties.java`
- Create: `guitar/src/test/java/com/example/guitar/crawler/config/GuitarCrawlerPropertiesTest.java`
- Modify: `guitar/src/test/java/com/example/guitar/schema/GuitarSchemaSqlTest.java`

- [ ] **Step 1: 写失败的配置边界测试**

```java
class GuitarCrawlerPropertiesTest {
    @Test
    void maxItemsMustStayBetweenOneAndFifty() {
        GuitarCrawlerProperties properties = new GuitarCrawlerProperties();
        assertThatThrownBy(() -> properties.setMaxItems(0))
                .isInstanceOf(IllegalArgumentException.class);
        properties.setMaxItems(50);
        assertThat(properties.getMaxItems()).isEqualTo(50);
        assertThatThrownBy(() -> properties.setMaxItems(51))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
```

同时在 `GuitarSchemaSqlTest` 断言：

```java
assertThat(schema).contains("CREATE TABLE IF NOT EXISTS guitar_sheet_source (");
assertThat(schema).contains("UNIQUE KEY uk_guitar_sheet_source_item (source_site, source_item_id)");
assertThat(schema).contains("UNIQUE KEY uk_guitar_sheet_source_sheet (sheet_id)");
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```powershell
mvn -pl guitar -am '-Dtest=GuitarCrawlerPropertiesTest,GuitarSchemaSqlTest' -DfailIfNoTests=false test
```

Expected: FAIL，`GuitarCrawlerProperties` 不存在且 schema 缺少来源表。

- [ ] **Step 3: 添加 Jsoup、配置绑定和来源表**

在 `guitar/pom.xml` 添加：

```xml
<dependency>
    <groupId>org.jsoup</groupId>
    <artifactId>jsoup</artifactId>
    <version>1.17.2</version>
</dependency>
```

配置类使用 `@Component`、`@ConfigurationProperties(prefix = "guitar.crawler")`，默认 `enabled=false`、`source=jitashe`、`maxItems=50`、`uploaderId=0`、`requestDelayMs=1500`、连接超时 3000ms、读取超时 10000ms。setter 拒绝空来源、非正超时、`maxItems` 超出 1-50。

在 schema 添加：

```sql
CREATE TABLE IF NOT EXISTS guitar_sheet_source (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    sheet_id BIGINT UNSIGNED NOT NULL,
    source_site VARCHAR(50) NOT NULL,
    source_item_id VARCHAR(100) NOT NULL,
    source_url VARCHAR(1000) NOT NULL,
    authorization_note VARCHAR(500) DEFAULT NULL,
    content_hash CHAR(64) NOT NULL,
    fetched_at DATETIME NOT NULL,
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_guitar_sheet_source_sheet (sheet_id),
    UNIQUE KEY uk_guitar_sheet_source_item (source_site, source_item_id),
    KEY idx_guitar_sheet_source_hash (content_hash),
    CONSTRAINT fk_guitar_sheet_source_sheet FOREIGN KEY (sheet_id) REFERENCES guitar_sheet (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

- [ ] **Step 4: 运行测试并确认通过**

Run: Task 1 Step 2 的命令。

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add guitar/pom.xml guitar/src/main/resources/application.yml guitar/src/main/resources/db/guitar-schema.sql guitar/src/main/java/com/example/guitar/crawler/config/GuitarCrawlerProperties.java guitar/src/test/java/com/example/guitar/crawler/config/GuitarCrawlerPropertiesTest.java guitar/src/test/java/com/example/guitar/schema/GuitarSchemaSqlTest.java
git commit -m "feat(guitar): configure authorized sheet crawler"
```

### Task 2: 吉他社 HTML 解析器

**Files:**
- Create: `guitar/src/main/java/com/example/guitar/crawler/model/SourceSheetCandidate.java`
- Create: `guitar/src/main/java/com/example/guitar/crawler/jitashe/JitasheParser.java`
- Create: `guitar/src/test/resources/crawler/jitashe-list.html`
- Create: `guitar/src/test/resources/crawler/jitashe-detail-images.html`
- Create: `guitar/src/test/resources/crawler/jitashe-detail-pdf.html`
- Create: `guitar/src/test/java/com/example/guitar/crawler/jitashe/JitasheParserTest.java`

- [ ] **Step 1: 写解析失败测试和固定 HTML 样本**

测试必须覆盖：

```java
@Test
void parsesChinesePopListInDocumentOrder() {
    List<SourceSheetCandidate> candidates = parser.parseList(load("jitashe-list.html"));
    assertThat(candidates).extracting(SourceSheetCandidate::getSourceItemId)
            .containsExactly("1405564", "1405563");
    assertThat(candidates.get(0).getSongName()).isEqualTo("同桌的你");
    assertThat(candidates.get(0).getSinger()).isEqualTo("老狼");
}

@Test
void parsesAndOrdersImageFiles() {
    SourceSheetCandidate result = parser.parseDetail(candidate(), load("jitashe-detail-images.html"));
    assertThat(result.getFileUrls()).containsExactly(
            "https://static.jitashe.org/sheet/1.jpg",
            "https://static.jitashe.org/sheet/2.png");
    assertThat(result.getFileMode()).isEqualTo(FileMode.IMAGES);
}
```

PDF 样本断言单文件映射为 `FileMode.PDF`。验证码、登录或无谱文件样本必须抛出 `JitasheParseException`。

- [ ] **Step 2: 运行测试并确认失败**

Run:

```powershell
mvn -pl guitar -am '-Dtest=JitasheParserTest' -DfailIfNoTests=false test
```

Expected: FAIL，解析器和模型不存在。

- [ ] **Step 3: 实现纯解析器**

`parseList` 只接受 `https://www.jitashe.org/tab/{digits}/`，从 URL 提取来源 ID，并按 DOM 顺序去重。`parseDetail` 只接受 `jitashe.org` 和 `static.jitashe.org` 的 HTTPS 文件 URL；清理标题中的“免费版”“原版吉他谱”等装饰词，但不破坏歌曲名。

候选模型字段固定为：

```java
String sourceItemId;
String sourceUrl;
String songName;
String singer;
String arranger;
String description;
String sourceCategory;
FileMode fileMode;
List<String> fileUrls;
```

- [ ] **Step 4: 运行测试并确认通过**

Run: Task 2 Step 2 的命令。

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add guitar/src/main/java/com/example/guitar/crawler guitar/src/test/java/com/example/guitar/crawler guitar/src/test/resources/crawler
git commit -m "feat(guitar): parse jitashe sheet pages"
```

### Task 3: 限速来源客户端与安全下载

**Files:**
- Create: `guitar/src/main/java/com/example/guitar/crawler/jitashe/JitasheSourceClient.java`
- Create: `guitar/src/main/java/com/example/guitar/crawler/jitashe/JitasheClientException.java`
- Create: `guitar/src/test/java/com/example/guitar/crawler/jitashe/JitasheSourceClientTest.java`

- [ ] **Step 1: 写失败测试**

使用本地 `HttpServer`，测试：

```java
@Test
void rejectsRedirectOutsideAllowedHosts() { /* 302 到 example.com，断言失败 */ }

@Test
void rejectsResponseLargerThanConfiguredLimit() { /* 超限流，断言停止读取 */ }

@Test
void appliesDelayBetweenRequests() { /* 注入 Clock/Sleeper，断言第二次请求等待 */ }
```

另外断言 User-Agent 为项目可识别值，4xx 不重试，5xx 最多重试两次。

- [ ] **Step 2: 运行测试并确认失败**

Run:

```powershell
mvn -pl guitar -am '-Dtest=JitasheSourceClientTest' -DfailIfNoTests=false test
```

Expected: FAIL，客户端不存在。

- [ ] **Step 3: 实现最小客户端**

使用 Jsoup 获取 HTML；二进制下载使用 `HttpURLConnection`，禁用自动跨域重定向并逐跳校验 HTTPS host 白名单。HTML 最大 2MB，单文件沿用 `SheetFileValidator` 上限，整批累计上限由导入服务控制。不得发送 Cookie、Authorization 或登录凭据。

- [ ] **Step 4: 运行测试并确认通过**

Run: Task 3 Step 2 的命令。

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add guitar/src/main/java/com/example/guitar/crawler/jitashe guitar/src/test/java/com/example/guitar/crawler/jitashe
git commit -m "feat(guitar): add rate-limited jitashe client"
```

### Task 4: 本地存储与文件格式校验

**Files:**
- Create: `guitar/src/main/java/com/example/guitar/crawler/model/DownloadedSheetFile.java`
- Create: `guitar/src/main/java/com/example/guitar/crawler/storage/LocalSheetStorage.java`
- Create: `guitar/src/main/java/com/example/guitar/crawler/storage/LocalSheetStorageException.java`
- Create: `guitar/src/test/java/com/example/guitar/crawler/storage/LocalSheetStorageTest.java`
- Modify: `guitar/.gitignore`

- [ ] **Step 1: 写失败测试**

使用 JUnit `@TempDir` 覆盖：

```java
@Test
void commitsValidatedFilesUnderGeneratedStorageUuid() { /* PDF 落到 local/{uuid}/pdf/01.pdf */ }

@Test
void rejectsFakePngAndDeletesTemporaryDirectory() { /* .png 内容非 PNG */ }

@Test
void resolveRejectsTraversalAndAbsolutePaths() { /* ../、C:\、根外 symlink 均失败 */ }
```

同时断言多图只允许 1-20 个、PDF 只能一个，文件名由服务器生成。

- [ ] **Step 2: 运行测试并确认失败**

Run:

```powershell
mvn -pl guitar -am '-Dtest=LocalSheetStorageTest' -DfailIfNoTests=false test
```

Expected: FAIL，本地存储不存在。

- [ ] **Step 3: 实现本地存储**

对象键格式固定：

```text
local/{storageUuid}/pdf/01.pdf
local/{storageUuid}/images/01.jpg
```

临时目录位于同一存储根目录的 `.tmp/{runUuid}`，以 `Files.move(..., ATOMIC_MOVE)` 提交；文件系统不支持原子移动时失败并清理，不静默降级为非原子覆盖。SHA-256 使用流式计算，整组摘要按排序后的“文件摘要 + 文件大小”计算。

将以下内容加入 `guitar/.gitignore`：

```gitignore
/data/
```

- [ ] **Step 4: 运行测试并确认通过**

Run: Task 4 Step 2 的命令。

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add guitar/.gitignore guitar/src/main/java/com/example/guitar/crawler/model guitar/src/main/java/com/example/guitar/crawler/storage guitar/src/test/java/com/example/guitar/crawler/storage
git commit -m "feat(guitar): store imported sheets locally"
```

### Task 5: 来源 DAO 与事务入库

**Files:**
- Create: `guitar/src/main/java/com/example/guitar/crawler/model/GuitarSheetSource.java`
- Create: `guitar/src/main/java/com/example/guitar/crawler/dao/GuitarSheetSourceDao.java`
- Create: `guitar/src/main/resources/mapper/crawler/GuitarSheetSourceMapper.xml`
- Create: `guitar/src/main/java/com/example/guitar/crawler/service/SheetImportPersistenceService.java`
- Create: `guitar/src/test/resources/sheet-import-h2.sql`
- Create: `guitar/src/test/java/com/example/guitar/crawler/service/SheetImportPersistenceServiceTest.java`

- [ ] **Step 1: 写失败的 H2 集成测试**

测试：

```java
@Test
void persistsPublishedSheetFilesAndSourceInOneTransaction() {
    Long id = service.persist(sheet(), files(), source());
    assertThat(status(id)).isEqualTo("PUBLISHED");
    assertThat(sourceCount("jitashe", "1405564")).isEqualTo(1);
}

@Test
void duplicateSourceRollsBackSheetAndFiles() { /* 唯一键冲突后三表无孤儿数据 */ }
```

DAO 还需提供：

```java
boolean existsBySource(String sourceSite, String sourceItemId);
boolean existsByContentHash(String contentHash);
int insert(GuitarSheetSource source);
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```powershell
mvn -pl guitar -am '-Dtest=SheetImportPersistenceServiceTest' -DfailIfNoTests=false test
```

Expected: FAIL，来源 DAO 和事务服务不存在。

- [ ] **Step 3: 实现 MyBatis XML 与事务服务**

事务服务复用 `GuitarSheetDao.insert` 和 `GuitarSheetFileDao.insertBatch`，随后写入来源；任一步返回数量不正确时抛出稳定异常并回滚。强制覆盖：

```java
sheet.setStatus("PUBLISHED");
source.setSheetId(sheet.getId());
```

- [ ] **Step 4: 运行测试并确认通过**

Run: Task 5 Step 2 的命令。

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add guitar/src/main/java/com/example/guitar/crawler guitar/src/main/resources/mapper/crawler guitar/src/test/java/com/example/guitar/crawler guitar/src/test/resources/sheet-import-h2.sql
git commit -m "feat(guitar): persist imported sheet provenance"
```

### Task 6: 导入编排与一次性启动器

**Files:**
- Create: `guitar/src/main/java/com/example/guitar/crawler/service/JitasheSheetImportService.java`
- Create: `guitar/src/main/java/com/example/guitar/crawler/service/SheetImportSummary.java`
- Create: `guitar/src/main/java/com/example/guitar/crawler/JitasheCrawlerCommandRunner.java`
- Create: `guitar/src/test/java/com/example/guitar/crawler/service/JitasheSheetImportServiceTest.java`
- Create: `guitar/src/test/java/com/example/guitar/crawler/JitasheCrawlerCommandRunnerTest.java`

- [ ] **Step 1: 写失败测试**

覆盖：

```java
@Test
void importsUntilFiftySuccessfulSheets() { /* 候选含失败项，成功数达到 50 后停止 */ }

@Test
void skipsExistingSourceBeforeDownloading() { /* verify(client, never()).download(...) */ }

@Test
void removesCommittedDirectoryWhenDatabaseWriteFails() { /* verify(storage).rollback(storageUuid) */ }

@Test
void disabledRunnerNeverCallsImporter() { /* 默认 enabled=false */ }
```

上传者不存在或 `uploaderId < 1` 时必须在第一次网络请求前失败。

- [ ] **Step 2: 运行测试并确认失败**

Run:

```powershell
mvn -pl guitar -am '-Dtest=JitasheSheetImportServiceTest,JitasheCrawlerCommandRunnerTest' -DfailIfNoTests=false test
```

Expected: FAIL，编排服务和启动器不存在。

- [ ] **Step 3: 实现编排和摘要**

摘要字段：

```java
int discovered;
int imported;
int duplicateSource;
int duplicateContent;
int failed;
List<String> failedSourceIds;
```

映射默认值固定为 `difficulty=INTERMEDIATE`、`keySignature=C`、`tuning=Standard`，类型按来源分类映射到现有枚举。任何超出现有字段边界的必填值都跳过，不截断。Runner 使用 `ApplicationRunner`，仅当 `enabled=true && source=jitashe` 时调用一次；异常只记录摘要，不导致 Spring Boot 启动失败。

- [ ] **Step 4: 运行测试并确认通过**

Run: Task 6 Step 2 的命令。

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add guitar/src/main/java/com/example/guitar/crawler guitar/src/test/java/com/example/guitar/crawler
git commit -m "feat(guitar): orchestrate authorized sheet imports"
```

### Task 7: 本地文件 URL 路由和安全下载

**Files:**
- Modify: `guitar/src/main/java/com/example/guitar/sheet/service/PublicOssSheetFileUrlService.java`
- Create: `guitar/src/main/java/com/example/guitar/sheet/service/RoutingSheetFileUrlService.java`
- Create: `guitar/src/main/java/com/example/guitar/sheet/controller/LocalSheetFileController.java`
- Modify: `guitar/src/main/java/com/example/guitar/sheet/dao/GuitarSheetFileDao.java`
- Modify: `guitar/src/main/resources/mapper/sheet/GuitarSheetFileMapper.xml`
- Create: `guitar/src/test/java/com/example/guitar/sheet/service/RoutingSheetFileUrlServiceTest.java`
- Create: `guitar/src/test/java/com/example/guitar/sheet/controller/LocalSheetFileControllerTest.java`

- [ ] **Step 1: 写失败测试**

断言：

```java
assertThat(service.getFileUrl("local/uuid/images/01.jpg"))
        .isEqualTo("/api/sheet-files/local/uuid/images/01.jpg");
verifyNoInteractions(ossService);
```

Controller 测试覆盖有效图片/PDF、数据库无记录返回 404、路径穿越返回 404、响应 `Content-Type` 与安全 `Content-Disposition`。

- [ ] **Step 2: 运行测试并确认失败**

Run:

```powershell
mvn -pl guitar -am '-Dtest=RoutingSheetFileUrlServiceTest,LocalSheetFileControllerTest' -DfailIfNoTests=false test
```

Expected: FAIL，路由服务和 Controller 不存在。

- [ ] **Step 3: 实现组合 URL 服务**

`RoutingSheetFileUrlService` 标记 `@Primary`：

```java
if (objectKey != null && objectKey.startsWith("local/")) {
    return "/api/sheet-files/" + encodeSegments(objectKey.substring("local/".length()));
}
return oss.getFileUrl(objectKey);
```

Controller 只在 `GuitarSheetFileDao.findByObjectKey("local/" + key)` 返回记录后调用 `LocalSheetStorage.resolve`。不要使用 `ResourceHttpRequestHandler` 暴露整个目录。

- [ ] **Step 4: 运行测试并确认通过**

Run: Task 7 Step 2 的命令。

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add guitar/src/main/java/com/example/guitar/sheet guitar/src/main/resources/mapper/sheet guitar/src/test/java/com/example/guitar/sheet
git commit -m "feat(guitar): serve imported local sheet files"
```

### Task 8: 文档、完整回归与受控冒烟

**Files:**
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `guitar/AGENTS.md`
- Modify: `guitar/README.md`

- [ ] **Step 1: 更新项目和模块文档**

明确记录：

- 功能仅针对用户已授权来源。
- 默认关闭，不绕过登录、验证码、付费墙或访问控制。
- 新表、配置项和 `guitar/data/sheets/` 数据目录。
- 准备专用上传者 ID 的方法，不提供或记录密码。
- 小批量命令：

```powershell
$env:GUITAR_CRAWLER_ENABLED='true'
$env:GUITAR_CRAWLER_UPLOADER_ID='<existing-user-id>'
$env:GUITAR_CRAWLER_MAX_ITEMS='3'
mvn -f guitar/pom.xml spring-boot:run
```

- 测试命令和重复运行预期。

- [ ] **Step 2: 运行聚焦测试**

Run:

```powershell
mvn -pl guitar -am '-Dtest=GuitarCrawlerPropertiesTest,JitasheParserTest,JitasheSourceClientTest,LocalSheetStorageTest,SheetImportPersistenceServiceTest,JitasheSheetImportServiceTest,JitasheCrawlerCommandRunnerTest,RoutingSheetFileUrlServiceTest,LocalSheetFileControllerTest' -DfailIfNoTests=false test
```

Expected: BUILD SUCCESS。

- [ ] **Step 3: 运行完整 Guitar 回归**

Run:

```powershell
mvn -pl guitar -am test
```

Expected: BUILD SUCCESS，现有 OSS 上传、认证、收藏和管理员测试保持通过。

- [ ] **Step 4: 检查敏感信息和工作区**

Run:

```powershell
rg -n "Cookie|Authorization|password|token|secret" guitar/src/main/java/com/example/guitar/crawler guitar/src/main/resources/application.yml
git status --short
```

Expected: 不存在打印或硬编码凭据；`guitar/data/` 不出现在状态中；只包含本任务文档和代码。

- [ ] **Step 5: 在用户提供有效本地数据库和上传者 ID 后执行 3 条受控冒烟**

先运行 `GET /api/health`，再启用 `max-items=3`。确认：

- 三份或候选耗尽数量的文件写入本地。
- `guitar_sheet.status='PUBLISHED'`。
- `guitar_sheet_source` 有来源 ID、URL、授权备注和 SHA-256。
- 首页能打开本地谱图/PDF。
- 第二次运行不会增加相同来源记录。

不得在测试输出或文档中记录数据库密码、Cookie 或任何授权凭据。

- [ ] **Step 6: 提交**

```powershell
git add AGENTS.md README.md guitar/AGENTS.md guitar/README.md
git commit -m "docs(guitar): document authorized sheet imports"
```
