# Stock Java Microservice Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the active `website/python-a` Python backend with a peer-level `stock` Spring Boot microservice while preserving port `5174`, the frontend, every existing API, JSON data, and Obsidian output.

**Architecture:** Add `stock` as a peer Maven module that owns HTTP controllers, business services, external API clients, compatible JSON repositories, Obsidian writers, and the unchanged static frontend. Migrate behavior through test-first vertical slices, then remove Python lifecycle management from `website` and let the root script orchestrate the two independent Java services.

**Tech Stack:** Java 8, Spring Boot 2.6.13, Spring MVC, Jackson, JUnit 5, AssertJ, Mockito, MockMvc, Maven Surefire 2.22.2, native HTML/CSS/JavaScript.

---

## File Map

New production files are grouped by responsibility:

- `stock/pom.xml`: independent Spring Boot module build.
- `stock/src/main/java/com/example/stock/StockApplication.java`: service entry point.
- `stock/src/main/java/com/example/stock/config/StockProperties.java`: port-independent data and external API configuration.
- `stock/src/main/java/com/example/stock/repository/JsonFileStore.java`: compatible, atomic, locked JSON list storage.
- `stock/src/main/java/com/example/stock/service/AccountService.java`: capital flow and snapshot calculations.
- `stock/src/main/java/com/example/stock/service/TradeService.java`: trades and parse-draft lifecycle.
- `stock/src/main/java/com/example/stock/service/StockMatchService.java`: stock-name matching and manual mappings.
- `stock/src/main/java/com/example/stock/service/WatchlistService.java`: compatible watchlist CRUD.
- `stock/src/main/java/com/example/stock/service/MarketAnalysisService.java`: deterministic quote/K-line normalization and scores.
- `stock/src/main/java/com/example/stock/service/StockMetadataService.java`: cached metadata normalization and fallback.
- `stock/src/main/java/com/example/stock/client/EastmoneyClient.java`: Eastmoney quote and K-line HTTP calls.
- `stock/src/main/java/com/example/stock/client/DeepSeekClient.java`: dimension-analysis call and strict JSON parsing.
- `stock/src/main/java/com/example/stock/client/VisionClient.java`: account/trade screenshot parsing.
- `stock/src/main/java/com/example/stock/obsidian/ObsidianTradingService.java`: daily review, stock note, and insight index.
- `stock/src/main/java/com/example/stock/obsidian/KnowledgeGraphService.java`: concept nodes and Markdown links.
- `stock/src/main/java/com/example/stock/service/StockReviewService.java`: legacy stock/daily review orchestration and compatible Markdown payloads.
- `stock/src/main/java/com/example/stock/controller/ResearchController.java`: health, watchlist, stock, and dimension-analysis endpoints.
- `stock/src/main/java/com/example/stock/controller/TradingController.java`: ledger, upload, drafts, and stock-match endpoints.
- `stock/src/main/java/com/example/stock/controller/ObsidianController.java`: review and insight endpoints.
- `stock/src/main/java/com/example/stock/controller/ApiExceptionHandler.java`: compatible error envelopes.
- `stock/src/main/resources/static/`: byte-equivalent migrated frontend.
- `stock/src/test/resources/contracts/`: compatible JSON and Markdown fixtures.
- `stock/src/test/java/com/example/stock/support/TestMaps.java`: Java 8 map fixture builder used by service tests.

Existing integration files changed at cutover:

- `pom.xml`: add peer module `stock`.
- `scripts/start-love5000.ps1`: start/reuse `stock`, then start `website`.
- `website/src/main/java/com/example/website/integration/PythonAAutoStartRunner.java`: delete.
- `website/src/test/java/com/example/website/integration/PythonAAutoStartRunnerTest.java`: delete.
- `website/src/main/resources/application.yml`: remove `python-a.auto-start`.
- Root and affected module `AGENTS.md` / `README.md`: document the new boundary and commands.

## Task 1: Bootstrap the Peer-Level Spring Boot Module

**Files:**
- Modify: `pom.xml`
- Create: `stock/pom.xml`
- Create: `stock/src/main/java/com/example/stock/StockApplication.java`
- Create: `stock/src/main/java/com/example/stock/controller/HealthController.java`
- Create: `stock/src/main/resources/application.yml`
- Create: `stock/src/test/java/com/example/stock/controller/HealthControllerTest.java`

- [ ] **Step 1: Add the failing health contract test**

```java
@WebMvcTest(HealthController.class)
class HealthControllerTest {
    @Autowired private MockMvc mockMvc;

    @Test
    void returnsCompatibleHealthEnvelope() throws Exception {
        mockMvc.perform(get("/api/health"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ok").value(true))
                .andExpect(jsonPath("$.success").value(true));
    }
}
```

- [ ] **Step 2: Add only the Maven module configuration needed to run the test**

Add `<module>stock</module>` to the root module list. `stock/pom.xml` must inherit `love530`, depend on `common`, `spring-boot-starter-web`, and `spring-boot-starter-test`, and configure `StockApplication` in `spring-boot-maven-plugin`.

- [ ] **Step 3: Run the test and verify RED**

Run: `mvn -pl stock -am -Dtest=HealthControllerTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: compilation fails because `HealthController` does not exist.

- [ ] **Step 4: Implement the application and minimal health controller**

```java
@SpringBootApplication
public class StockApplication {
    public static void main(String[] args) {
        SpringApplication.run(StockApplication.class, args);
    }
}

@RestController
public class HealthController {
    @GetMapping("/api/health")
    public Map<String, Object> health() {
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("ok", true);
        response.put("success", true);
        response.put("time", OffsetDateTime.now().toString());
        response.put("data_source", "东方财富 push2 / push2his");
        return response;
    }
}
```

Set `server.port: 5174`, UTF-8 encoding, and multipart limits in `application.yml`.

- [ ] **Step 5: Run GREEN and commit**

Run: `mvn -pl stock -am -Dtest=HealthControllerTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: `HealthControllerTest` passes.

Commit: `git commit -m "feat: bootstrap stock java microservice"`

## Task 2: Add Compatible JSON Storage and Data Configuration

**Files:**
- Create: `stock/src/main/java/com/example/stock/config/StockProperties.java`
- Create: `stock/src/main/java/com/example/stock/repository/JsonFileStore.java`
- Create: `stock/src/main/java/com/example/stock/repository/StoreSupport.java`
- Create: `stock/src/test/java/com/example/stock/repository/JsonFileStoreTest.java`
- Create: `stock/src/test/java/com/example/stock/support/TestMaps.java`
- Create: `stock/src/test/resources/contracts/trades.json`

- [ ] **Step 1: Write failing storage tests**

Tests must prove these exact behaviors:

```java
assertThat(store.readList("missing.json")).isEmpty();
assertThat(store.append("trades.json", row)).isEqualTo(row);
assertThat(store.readList("trades.json")).containsExactly(row);
assertThat(StoreSupport.newId("tr", "2026-06-05", 7)).isEqualTo("tr_20260605_007");
assertThat(StoreSupport.filterByDate(rows, "2026-06-05"))
        .extracting(item -> item.get("id")).containsExactly("a", "b");
```

Add a corrupt JSON test that expects the source to be renamed to `trades.json.corrupt-<timestamp>` and an `IllegalArgumentException` containing `JSON 文件损坏`.

Create `TestMaps.mapOf(Object... entries)` with an even-entry-count check and `LinkedHashMap<String, Object>` output so every later test uses one shared Java 8 fixture builder.

- [ ] **Step 2: Run RED**

Run: `mvn -pl stock -am -Dtest=JsonFileStoreTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: compilation fails because storage classes do not exist.

- [ ] **Step 3: Implement configuration precedence**

`StockProperties.resolveObsidianRoot()` must resolve in this order:

```text
STOCK_OBSIDIAN_ROOT
ASHARE_OBSIDIAN_ROOT
<repository>/stock/obsidian-vault/A股AI
<module>/obsidian-vault/A股AI
```

Expose `dataRoot()` as `obsidianRoot.resolve("data")`.

- [ ] **Step 4: Implement locked atomic list storage**

Use `ObjectMapper`, one `ReentrantReadWriteLock` per normalized file path, `Files.move(temp, target, REPLACE_EXISTING, ATOMIC_MOVE)`, and fall back to `REPLACE_EXISTING` when atomic move is unsupported. `append` must hold the write lock across read-modify-write.

- [ ] **Step 5: Run GREEN and commit**

Run: `mvn -pl stock -am -Dtest=JsonFileStoreTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: all storage tests pass without touching the real vault.

Commit: `git commit -m "feat: add compatible stock json storage"`

## Task 3: Port Account Ledger Behavior

**Files:**
- Create: `stock/src/main/java/com/example/stock/service/AccountService.java`
- Create: `stock/src/test/java/com/example/stock/service/AccountServiceTest.java`

- [ ] **Step 1: Write failing account tests**

Port the three current Python cases and add invalid-flow coverage:

```java
Map<String, Object> flow = service.addCapitalFlow(mapOf(
        "date", "2026-06-01", "type", "initial", "amount", 16000));
assertThat(flow.get("id")).isEqualTo("cf_20260601_001");
assertThat(service.currentPrincipal("2026-06-05")).isEqualByComparingTo("16000.00");

Map<String, Object> snapshot = service.addAccountSnapshot(mapOf(
        "trade_date", "2026-06-05", "total_assets", 15909.86));
assertThat(snapshot.get("account_profit")).isEqualTo(-90.14);
assertThat(snapshot.get("account_profit_rate")).isEqualTo(-0.0056);
```

Verify dashboard returns the last snapshot for the requested date and rejects a flow type outside `initial`, `deposit`, `withdraw`, `adjustment`.

- [ ] **Step 2: Run RED**

Run: `mvn -pl stock -am -Dtest=AccountServiceTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: compilation fails because `AccountService` does not exist.

- [ ] **Step 3: Implement the account service**

Use `capital_flows.json` and `account_snapshots.json`. Preserve current IDs, `source=manual`, `confirmed=true`, four-decimal optional numeric normalization, principal sign rules, and the dashboard keys `principal`, `snapshot`, `snapshots`, `capital_flows`.

- [ ] **Step 4: Run GREEN and commit**

Run: `mvn -pl stock -am -Dtest=AccountServiceTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: account tests pass.

Commit: `git commit -m "feat: port stock account ledger"`

## Task 4: Port Trades, Parse Drafts, and Stock Matching

**Files:**
- Create: `stock/src/main/java/com/example/stock/service/TradeService.java`
- Create: `stock/src/main/java/com/example/stock/service/StockMatchService.java`
- Create: `stock/src/test/java/com/example/stock/service/TradeServiceTest.java`
- Create: `stock/src/test/java/com/example/stock/service/StockMatchServiceTest.java`

- [ ] **Step 1: Write failing trade tests**

Port tests for side normalization, date filtering, draft confirmation, and rejection. Assert `买入`, `买`, and `buy` normalize to `buy`; `卖出`, `卖`, and `sell` normalize to `sell`.

```java
Map<String, Object> result = service.confirmDraft(draftId, mapOf("trades", trades));
assertThat(((Map<?, ?>) result.get("draft")).get("status")).isEqualTo("confirmed");
assertThat((List<?>) result.get("created_trades")).hasSize(1);
```

- [ ] **Step 2: Write failing stock-match tests**

Verify unique exact match, one fuzzy match, multiple matches, unknown names, and persistence of `通信ETF国泰 -> 159510` in `stock_name_mappings.json`.

- [ ] **Step 3: Run RED**

Run: `mvn -pl stock -am -Dtest=TradeServiceTest,StockMatchServiceTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: compilation fails because both services are missing.

- [ ] **Step 4: Implement minimal compatible services**

Use `trades.json` and `parse_drafts.json`. Preserve `tr_`, `pd_` IDs, input fields, `source`, `confirmed`, timestamps, draft statuses, warnings, and `created_trades`. Reject missing trade datetime/name, invalid side, invalid numbers, unsupported draft type, and unknown draft ID with compatible messages.

- [ ] **Step 5: Run GREEN and commit**

Run: `mvn -pl stock -am -Dtest=TradeServiceTest,StockMatchServiceTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: both suites pass.

Commit: `git commit -m "feat: port stock trade and matching services"`

## Task 5: Port Obsidian and Knowledge Graph Writers

**Files:**
- Create: `stock/src/main/java/com/example/stock/obsidian/ObsidianTradingService.java`
- Create: `stock/src/main/java/com/example/stock/obsidian/KnowledgeGraphService.java`
- Create: `stock/src/main/java/com/example/stock/service/StockMetadataService.java`
- Create: `stock/src/main/java/com/example/stock/service/StockReviewService.java`
- Create: `stock/src/test/java/com/example/stock/obsidian/ObsidianTradingServiceTest.java`
- Create: `stock/src/test/java/com/example/stock/obsidian/KnowledgeGraphServiceTest.java`
- Create: `stock/src/test/java/com/example/stock/service/StockMetadataServiceTest.java`
- Create: `stock/src/test/java/com/example/stock/service/StockReviewServiceTest.java`
- Create: `stock/src/test/resources/contracts/daily-review.md`

- [ ] **Step 1: Write failing Markdown compatibility tests**

Use `@TempDir` and assert generated files contain:

```text
# 2026-06-05 交易复盘
## 账户快照
## 今日交易
非投资建议
```

Pre-create a stock note with `## 我的手写心得` and `这里别覆盖。`, update it, and assert both the new system section and manual text remain.

- [ ] **Step 2: Write failing knowledge graph and metadata tests**

Port the existing cases for industry `电池`, concepts `储能`, high-turnover risk nodes, cached metadata precedence, and normalized fallback. Assert the Markdown section includes `[[002580-圣阳股份]]`, `[[行业-电池]]`, `[[概念-储能]]`, and `[[风险模式-高换手]]`.

Add `StockReviewServiceTest` for both legacy operations. The stock review case must assert the daily operation file, long-term stock note, metadata fields, and knowledge-graph links are written. The general daily review case must assert the returned `vault_root`, review path, date, title, and non-investment-advice text match the Python response and Markdown format.

- [ ] **Step 3: Run RED**

Run: `mvn -pl stock -am -Dtest=ObsidianTradingServiceTest,KnowledgeGraphServiceTest,StockMetadataServiceTest,StockReviewServiceTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: compilation fails because the writers and metadata service are missing.

- [ ] **Step 4: Implement exact Markdown sections and cached metadata behavior**

Use UTF-8, sanitize path components, create only directories under the configured vault, and preserve manual content from its heading to EOF. Metadata reads `data/stock-metadata/{code}.json` before fallback and normalizes a scalar concept to a one-element list. `StockReviewService` must port `write_stock_daily_review` and `write_daily_review` orchestration from `server.py` without changing section order or response keys.

- [ ] **Step 5: Run GREEN and commit**

Run: `mvn -pl stock -am -Dtest=ObsidianTradingServiceTest,KnowledgeGraphServiceTest,StockMetadataServiceTest,StockReviewServiceTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: all file tests pass against temporary directories.

Commit: `git commit -m "feat: port stock obsidian services"`

## Task 6: Port Watchlist and Deterministic Market Analysis

**Files:**
- Create: `stock/src/main/java/com/example/stock/service/WatchlistService.java`
- Create: `stock/src/main/java/com/example/stock/service/MarketMath.java`
- Create: `stock/src/main/java/com/example/stock/service/MarketAnalysisService.java`
- Create: `stock/src/main/java/com/example/stock/client/MarketDataClient.java`
- Create: `stock/src/main/java/com/example/stock/client/EastmoneyClient.java`
- Create: `stock/src/test/java/com/example/stock/service/WatchlistServiceTest.java`
- Create: `stock/src/test/java/com/example/stock/service/MarketMathTest.java`
- Create: `stock/src/test/java/com/example/stock/service/MarketAnalysisServiceTest.java`
- Create: `stock/src/test/java/com/example/stock/client/EastmoneyClientTest.java`
- Create: `stock/src/test/resources/contracts/eastmoney-quote.json`
- Create: `stock/src/test/resources/contracts/eastmoney-kline.json`

- [ ] **Step 1: Capture deterministic expected values from the current Python implementation**

Fixtures must cover `002580`, market secid `0.002580`, scaled price/percent, parsed K-lines, MA5/MA10/MA30, turnover percentile, trend score, distribution score, risk, and status. Store only public mock payloads and expected JSON; do not call Eastmoney from tests.

- [ ] **Step 2: Write failing watchlist and math tests**

```java
assertThat(MarketMath.secidForCode("600379")).isEqualTo("1.600379");
assertThat(MarketMath.secidForCode("002580")).isEqualTo("0.002580");
assertThat(MarketMath.scaledPrice(3417)).isEqualTo(34.17);
assertThat(MarketMath.movingAverage(closes, 5)).hasSameSizeAs(closes);
```

Watchlist tests must cover missing-file default, add, duplicate code rejection, delete, and UTF-8 persistence.

- [ ] **Step 3: Write failing service and HTTP-client tests**

Inject a fake `MarketDataClient` returning contract fixtures and assert the composed stock response matches the expected snapshot fields. Use `MockRestServiceServer` to verify Eastmoney headers, URL fields, retryable failure, and empty-data rejection.

- [ ] **Step 4: Run RED**

Run: `mvn -pl stock -am -Dtest=WatchlistServiceTest,MarketMathTest,MarketAnalysisServiceTest,EastmoneyClientTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: compilation fails because the market components do not exist.

- [ ] **Step 5: Implement compatible calculations and client behavior**

Port the current Python functions without algebraic refactoring: parsing, scaling, averages, percentile, trend state/score, distribution score, risk classification, status, quote URL, K-line URL, and response assembly. Preserve browser headers, 12-second read timeout, two attempts, and `DataSourceException` for invalid upstream payloads.

- [ ] **Step 6: Run GREEN and commit**

Run: `mvn -pl stock -am -Dtest=WatchlistServiceTest,MarketMathTest,MarketAnalysisServiceTest,EastmoneyClientTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: fixtures produce the same expected values as Python.

Commit: `git commit -m "feat: port stock market research"`

## Task 7: Port DeepSeek and Vision Integrations

**Files:**
- Create: `stock/src/main/java/com/example/stock/client/DeepSeekClient.java`
- Create: `stock/src/main/java/com/example/stock/client/VisionClient.java`
- Create: `stock/src/main/java/com/example/stock/service/DimensionAnalysisService.java`
- Create: `stock/src/test/java/com/example/stock/client/DeepSeekClientTest.java`
- Create: `stock/src/test/java/com/example/stock/client/VisionClientTest.java`
- Create: `stock/src/test/java/com/example/stock/service/DimensionAnalysisServiceTest.java`

- [ ] **Step 1: Write failing prompt and disabled-state tests**

Assert dimension prompts contain `每个字段使用中文` and `不输出确定性买卖指令`. Assert account prompts mention `总资产`, `持仓`, and `严格 JSON`; trade prompts mention `成交时间`, `成交价格`, and the missing-code rule. Calling Vision without a key must throw an exception containing `VISION_API_KEY`.

- [ ] **Step 2: Write failing HTTP tests**

Use `MockRestServiceServer` to assert bearer headers, Chat Completions paths, configured model, base64 data URL, 90-second timeout configuration, DeepSeek JSON extraction, Vision JSON extraction, and upstream error detail preservation.

- [ ] **Step 3: Run RED**

Run: `mvn -pl stock -am -Dtest=DeepSeekClientTest,VisionClientTest,DimensionAnalysisServiceTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: compilation fails because the clients are missing.

- [ ] **Step 4: Implement injectable clients and analysis orchestration**

Read existing environment names unchanged: `DEEPSEEK_API_KEY`, `DEEPSEEK_API_BASE`, `DEEPSEEK_MODEL`, `VISION_API_KEY`, `VISION_API_BASE`, and `VISION_MODEL`. Continue reading ignored `stock/deepseek.local.json`, then legacy `website/python-a/deepseek.local.json`, only as compatibility fallbacks when the environment key is empty.

- [ ] **Step 5: Run GREEN and commit**

Run: `mvn -pl stock -am -Dtest=DeepSeekClientTest,VisionClientTest,DimensionAnalysisServiceTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: integration tests pass without network access.

Commit: `git commit -m "feat: port stock ai integrations"`

## Task 8: Expose the Complete Compatible HTTP API

**Files:**
- Create: `stock/src/main/java/com/example/stock/controller/ResearchController.java`
- Create: `stock/src/main/java/com/example/stock/controller/TradingController.java`
- Create: `stock/src/main/java/com/example/stock/controller/ObsidianController.java`
- Create: `stock/src/main/java/com/example/stock/controller/ApiExceptionHandler.java`
- Create: `stock/src/test/java/com/example/stock/controller/ResearchControllerTest.java`
- Create: `stock/src/test/java/com/example/stock/controller/TradingControllerTest.java`
- Create: `stock/src/test/java/com/example/stock/controller/ObsidianControllerTest.java`
- Create: `stock/src/test/java/com/example/stock/controller/ApiExceptionHandlerTest.java`

- [ ] **Step 1: Write failing MockMvc research tests**

Cover `GET/POST/DELETE /api/watchlist`, `GET /api/stock`, and `POST /api/ai/dimension-analysis`. Assert service calls receive unchanged fields and responses contain compatible `ok`/payload keys. Assert upstream market failure maps to HTTP 502.

- [ ] **Step 2: Write failing MockMvc trading tests**

Cover all ledger endpoints, parse-draft confirm/reject, stock match, and both multipart screenshot routes. A multipart test must submit field `file` plus `trade_date=2026-06-05` and assert bytes and MIME type reach `VisionClient`.

- [ ] **Step 3: Write failing MockMvc Obsidian and error tests**

Cover both legacy Obsidian endpoints, daily trading review, and insight update. Invalid input must return HTTP 400 with:

```json
{"ok":false,"success":false,"error":"detail","message":"detail"}
```

- [ ] **Step 4: Run RED**

Run: `mvn -pl stock -am -Dtest=*ControllerTest,ApiExceptionHandlerTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: compilation fails because controllers are missing.

- [ ] **Step 5: Implement thin controllers and global exception mapping**

Controllers may parse HTTP input and compose envelopes but must delegate calculations, storage, Markdown, and HTTP clients. Add the complete route list from the approved spec, including `/api/trading/stock-match`.

- [ ] **Step 6: Run GREEN and commit**

Run: `mvn -pl stock -am -Dtest=*ControllerTest,ApiExceptionHandlerTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: every route contract passes.

Commit: `git commit -m "feat: expose stock compatible api"`

## Task 9: Migrate the Frontend Without Behavior Changes

**Files:**
- Create: `stock/src/main/resources/static/index.html`
- Create: `stock/src/main/resources/static/app.js`
- Create: `stock/src/main/resources/static/styles.css`
- Create: `stock/src/test/java/com/example/stock/StaticFrontendTest.java`

- [ ] **Step 1: Write failing static resource tests**

Assert `/` returns 200 and contains `股票研究` and `交易复盘`. Read classpath `app.js` and assert it contains every existing relative API path, `http://127.0.0.1:8090`, `全程使用中文`, and the no-English-title/report constraints.

- [ ] **Step 2: Run RED**

Run: `mvn -pl stock -am -Dtest=StaticFrontendTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: `/` is 404 because static assets are absent.

- [ ] **Step 3: Copy the existing frontend byte-for-byte**

Copy only `website/python-a/index.html`, `app.js`, and `styles.css` into `stock/src/main/resources/static/`. Do not redesign, reformat, rename element IDs, or change API paths.

- [ ] **Step 4: Run GREEN and commit**

Run: `mvn -pl stock -am -Dtest=StaticFrontendTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: static resource tests pass.

Commit: `git commit -m "feat: migrate stock research frontend"`

## Task 10: Add Safe Data Migration

**Files:**
- Create: `scripts/migrate-python-a-to-stock.ps1`
- Modify: `.gitignore`
- Create: `stock/src/test/java/com/example/stock/migration/DataCompatibilityTest.java`
- Create: `stock/obsidian-vault/A股AI/README.md`

- [ ] **Step 1: Write failing compatibility tests against copied fixtures**

Load representative watchlist, trade, snapshot, metadata, and Markdown files copied into a temporary directory. Assert Java repositories parse every JSON file and Obsidian services preserve existing manual sections after an update.

- [ ] **Step 2: Run RED**

Run: `mvn -pl stock -am -Dtest=DataCompatibilityTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: test fails because migration fixtures/script are absent.

- [ ] **Step 3: Implement an idempotent PowerShell migration script**

The script must resolve absolute source and target paths, refuse to run while `5174/api/health` identifies the Python implementation, use `Copy-Item` without overwriting existing files, compare source/target relative file counts, and parse every target `data/*.json` with `ConvertFrom-Json`. It must never delete the source directory.

Extend `.gitignore` for `stock/deepseek.local.json`, `stock/.env`, service logs, generated corrupt backups, and local vault data while keeping `stock/obsidian-vault/A股AI/README.md` trackable.

- [ ] **Step 4: Run migration into a temporary target and verify GREEN**

Run: `powershell -NoProfile -File scripts/migrate-python-a-to-stock.ps1 -Source website/python-a/obsidian-vault/A股AI -Target $env:TEMP/love5000-stock-test`

Then run: `mvn -pl stock -am -Dtest=DataCompatibilityTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: migration exits 0 and compatibility tests pass.

- [ ] **Step 5: Commit**

Commit: `git commit -m "feat: add stock data migration"`

## Task 11: Cut Over Startup Ownership and Documentation

**Files:**
- Modify: `scripts/start-love5000.ps1`
- Delete: `website/src/main/java/com/example/website/integration/PythonAAutoStartRunner.java`
- Delete: `website/src/test/java/com/example/website/integration/PythonAAutoStartRunnerTest.java`
- Modify: `website/src/main/resources/application.yml`
- Modify: `website/src/test/java/com/example/website/WebsiteApplicationTests.java`
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `website/AGENTS.md`
- Modify: `website/README.md`
- Create: `stock/AGENTS.md`
- Create: `stock/README.md`

- [ ] **Step 1: Write the failing startup-script assertions**

Add Pester-free PowerShell assertions in `scripts/tests/start-love5000-stock.test.ps1` that read the script and require `stock`, `mvn -pl stock -am spring-boot:run`, port `5174`, and `/api/health`, while rejecting `python server.py` and `website\python-a` as active startup paths.

- [ ] **Step 2: Run RED**

Run: `powershell -NoProfile -File scripts/tests/start-love5000-stock.test.ps1`

Expected: fails because the script still starts Python.

- [ ] **Step 3: Update orchestration and remove website lifecycle ownership**

The root script must start or reuse `stock`, wait for health, then start `website`. Remove `python-a.auto-start` YAML, runner, runner test, and the disabled-property entry from `WebsiteApplicationTests`. Do not add a Java `StockAutoStartRunner` to `website`.

- [ ] **Step 4: Update all required documentation**

Document `stock` as a peer Java module, port `5174`, commands, environment variables, API list, data root, migration command, test commands, and deployment boundary. Mark `website/python-a` as legacy rollback code rather than the active service. Keep the homepage URL unchanged.

- [ ] **Step 5: Run GREEN and module tests**

Run:

```text
powershell -NoProfile -File scripts/tests/start-love5000-stock.test.ps1
mvn -pl website -am test
mvn -pl stock -am test
```

Expected: script assertions and both Maven test sets pass.

- [ ] **Step 6: Commit**

Commit: `git commit -m "feat: cut over to stock java service"`

## Task 12: Full Verification and Local Handoff

**Files:**
- Modify only files required by failures found in this task, with a new failing regression test before each production fix.

- [ ] **Step 1: Verify the legacy Python baseline remains readable**

Run: `python -m unittest discover -s tests -v` from `website/python-a`.

Expected: the existing 28 tests pass; the `cgi` deprecation warning may remain because legacy code is no longer active.

- [ ] **Step 2: Run focused and full Maven verification**

Run:

```text
mvn -pl stock -am test
mvn -pl website -am test
mvn test
```

Expected: all commands exit 0 with zero failures.

- [ ] **Step 3: Start `stock` on `5174` with a temporary vault**

Set `STOCK_OBSIDIAN_ROOT` to a temporary directory and run `mvn -pl stock -am spring-boot:run`. Do not point smoke tests at the user's real vault.

- [ ] **Step 4: Verify HTTP smoke contracts**

Check:

```text
GET  http://127.0.0.1:5174/
GET  http://127.0.0.1:5174/api/health
GET  http://127.0.0.1:5174/api/watchlist
POST http://127.0.0.1:5174/api/trading/capital-flows
POST http://127.0.0.1:5174/api/trading/trades
POST http://127.0.0.1:5174/api/trading/daily-review
```

Expected: successful responses include `ok: true` or `success: true`; writes appear only under the temporary vault.

- [ ] **Step 5: Browser smoke test**

Open `http://127.0.0.1:5174/` and verify the stock research view loads, the trading-review tab opens, no layout overlap occurs on desktop/mobile, and relative API requests target port `5174`. Since frontend assets are unchanged, visual differences are regressions.

- [ ] **Step 6: Inspect repository state and secrets**

Run `git diff --check`, `git status --short`, and secret-pattern searches. Confirm no `deepseek.local.json`, `.env`, logs, generated vault data, screenshots, keys, or user-owned untracked Python files are staged.

- [ ] **Step 7: Commit verification-only fixes, if any**

For each discovered issue, add a failing regression test, implement the minimal fix, rerun the affected suite, then commit with a specific message. If no fixes are needed, do not create an empty commit.

## Plan Self-Review

- The plan covers every API listed in the approved design.
- Storage, account, trade, metadata, knowledge graph, AI, screenshot parsing, static frontend, migration, startup, and documentation have explicit tasks.
- Every production behavior starts with a failing test and a RED verification command.
- External network calls and the user's real Obsidian vault are excluded from automated tests.
- `stock` is peer-level; `website` has no Java dependency on it and does not own its lifecycle.
- Existing untracked Python files are explicitly preserved.
