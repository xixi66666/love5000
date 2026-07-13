# Python-A Stock Research Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add lazy-loaded single-stock valuation, capital, research-report, and announcement data to `website/python-a`, with truthful source fallback, AI context, and Obsidian snapshots.

**Architecture:** Add focused standard-library Provider classes behind `StockResearchService`. The service owns per-block caching, fallback, and compact snapshots; `server.py` exposes three research routes and reuses snapshots for AI and review saves. The existing three-column UI gains overview, capital, and events tabs without changing existing watchlist or trading behavior.

**Tech Stack:** Python 3.9+, `urllib`, `ThreadingHTTPServer`, `unittest`, HTML, CSS, vanilla JavaScript, Node syntax checks, Playwright browser verification.

---

## File Structure

Create:

```text
website/python-a/services/research_provider.py
website/python-a/services/tencent_quote_provider.py
website/python-a/services/eastmoney_research_provider.py
website/python-a/services/sina_fund_flow_provider.py
website/python-a/services/cninfo_announcement_provider.py
website/python-a/services/stock_research_service.py
website/python-a/tests/test_research_providers.py
website/python-a/tests/test_stock_research_service.py
website/python-a/tests/test_stock_research_server.py
```

Modify:

```text
website/python-a/server.py
website/python-a/index.html
website/python-a/app.js
website/python-a/styles.css
website/python-a/tests/test_server_upload.py
website/python-a/README.md
website/python-a/AGENTS.md
website/README.md
website/AGENTS.md
README.md
AGENTS.md
```

Responsibilities:

- `research_provider.py`: HTTP client, provider exceptions, response block builders, safe URL validation, and Eastmoney rate limiter.
- Provider files: one external source per file, including parsing and unit normalization.
- `stock_research_service.py`: section orchestration, cache, fallback, pagination, and compact snapshot.
- `server.py`: route parsing and integration with existing AI and Obsidian flows.
- `index.html`, `app.js`, `styles.css`: research tabs, lazy loading, source metadata, responsive states.

## Task 1: Provider Contract and Tencent Overview

**Files:**
- Create: `website/python-a/services/research_provider.py`
- Create: `website/python-a/services/tencent_quote_provider.py`
- Create: `website/python-a/tests/test_research_providers.py`

- [ ] **Step 1: Write failing provider contract and Tencent parsing tests**

Add tests covering six-digit validation, safe URL filtering, Shenzhen/Shanghai/Beijing prefixes, GBK quote parsing, null values, units, provider metadata, and network errors. Use an injected fake text client:

```python
class FakeTextClient:
    def __init__(self, payload):
        self.payload = payload
        self.urls = []

    def get_text(self, url, headers=None, encoding="utf-8", timeout=15):
        self.urls.append(url)
        return self.payload


def test_tencent_quote_provider_parses_overview(self):
    values = [""] * 88
    values[1] = "圣阳股份"
    values[3] = "34.17"
    values[30] = "20260713143000"
    values[38] = "12.40"
    values[39] = "26.80"
    values[43] = "5.30"
    values[44] = "91.20"
    values[45] = "88.10"
    values[46] = "2.35"
    values[47] = "37.59"
    values[48] = "30.75"
    values[49] = "1.42"
    payload = 'v_sz002580="' + "~".join(values) + '";'

    provider = TencentQuoteProvider(FakeTextClient(payload))
    result = provider.fetch("002580")

    assert result["provider"] == "tencent"
    assert result["data_date"] == "2026-07-13"
    assert result["data"]["pe_ttm"] == 26.8
    assert result["data"]["market_cap_yi"] == 91.2
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
cd website/python-a
python -m unittest tests.test_research_providers -v
```

Expected: import failure because provider modules do not exist.

- [ ] **Step 3: Implement the provider contract and Tencent provider**

Implement Python 3.9-compatible APIs:

```python
class ResearchProviderError(RuntimeError):
    def __init__(self, message, retryable=True, status_code=None):
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code


def validate_stock_code(code):
    if not re.fullmatch(r"\d{6}", str(code or "")):
        raise ValueError("股票代码必须是 6 位数字")
    return str(code)


def success_block(provider, data, data_date=None, fallback_used=False):
    return {
        "success": True,
        "provider": provider,
        "fallback_used": fallback_used,
        "data_date": data_date,
        "fetched_at": now_iso(),
        "data": data,
    }
```

`TencentQuoteProvider.fetch(code)` must return `price`, `pe_ttm`, `pb`, `market_cap_yi`, `float_market_cap_yi`, `turnover_rate`, `amplitude`, `limit_up`, `limit_down`, and `volume_ratio`. Empty or invalid upstream values become `None`, never numeric zero placeholders.

- [ ] **Step 4: Run the tests and verify GREEN**

Run the focused unittest command. Expected: all provider contract and Tencent tests pass.

- [ ] **Step 5: Commit Task 1**

```bash
git add website/python-a/services/research_provider.py website/python-a/services/tencent_quote_provider.py website/python-a/tests/test_research_providers.py
git commit -m "feat: add python-a research provider contract"
```

## Task 2: Eastmoney, Sina, and CNInfo Providers

**Files:**
- Create: `website/python-a/services/eastmoney_research_provider.py`
- Create: `website/python-a/services/sina_fund_flow_provider.py`
- Create: `website/python-a/services/cninfo_announcement_provider.py`
- Modify: `website/python-a/tests/test_research_providers.py`

- [ ] **Step 1: Add failing parser and limiter tests**

Add deterministic fixtures for:

- Eastmoney overview fallback fields.
- 120-day fund flow.
- Margin trading.
- Shareholder count.
- Lockup expiry.
- Research reports.
- Sina fund-flow fallback.
- CNInfo announcements.
- Eastmoney rate limiter serialization with a fake clock and fake sleep.

Assert each provider returns normalized keys and the actual provider name. Assert announcement URLs reject non-HTTPS or unknown domains.

- [ ] **Step 2: Run focused tests and verify RED**

Run `python -m unittest tests.test_research_providers -v`. Expected: new provider imports or assertions fail.

- [ ] **Step 3: Implement thread-safe Eastmoney access**

Implement `EastmoneyRateLimiter` with `threading.Lock`, monotonic time, and injected sleep. All Eastmoney provider calls must pass through it. Retry network errors, `429`, and `5xx` at most twice; surface `403` as non-retryable so orchestration can fall back immediately.

- [ ] **Step 4: Implement source-specific providers**

Use the reviewed `a-stock-data` endpoints, while preserving TLS verification and standard-library-only dependencies:

```text
Tencent qt.gtimg.cn                     overview primary
Eastmoney push2                         overview fallback
Eastmoney push2his                      fund flow primary
Eastmoney datacenter-web                margin/shareholders/lockup
Eastmoney reportapi                     reports
Sina MoneyFlow.ssl_qsfx_zjlrqs          fund flow fallback
CNInfo announcement/query               announcement primary
SZSE/Eastmoney announcement endpoints   announcement fallback
```

Each parser must call `raise_for_invalid_payload` equivalents and distinguish empty valid results from malformed responses.

- [ ] **Step 5: Run focused tests and verify GREEN**

Expected: all provider tests pass without real network requests.

- [ ] **Step 6: Commit Task 2**

```bash
git add website/python-a/services/eastmoney_research_provider.py website/python-a/services/sina_fund_flow_provider.py website/python-a/services/cninfo_announcement_provider.py website/python-a/tests/test_research_providers.py
git commit -m "feat: add python-a stock research data providers"
```

## Task 3: Research Orchestration, Cache, Fallback, and Snapshot

**Files:**
- Create: `website/python-a/services/stock_research_service.py`
- Create: `website/python-a/tests/test_stock_research_service.py`

- [ ] **Step 1: Write failing service tests**

Use Fake Providers with call counters. Cover:

- Overview: Tencent succeeds; Tencent fails and Eastmoney succeeds.
- Metadata source remains independent from valuation source.
- Capital blocks can have mixed providers.
- Fund-flow fallback returns `provider=sina` and `fallback_used=true`.
- A failed block does not fail the section.
- Cache TTL and `force=True` behavior.
- Events pagination by `kind`, `page`, and `page_size`.
- Compact snapshot contains values, sources, dates, and at most five reports and five announcements.

```python
def test_fund_flow_fallback_reports_actual_source(self):
    service = make_service(eastmoney=BrokenProvider(), sina=FakeSinaProvider())
    result = service.get_capital("002580")
    block = result["blocks"]["fund_flow"]
    self.assertTrue(block["success"])
    self.assertEqual(block["provider"], "sina")
    self.assertTrue(block["fallback_used"])
```

- [ ] **Step 2: Run service tests and verify RED**

Expected: module import failure.

- [ ] **Step 3: Implement `StockResearchService`**

Implement:

```python
get_overview(code, force=False)
get_capital(code, force=False)
get_events(code, kind="all", page=1, page_size=10, force=False)
build_snapshot(code, load_missing=True)
```

Use per-block cache keys `(code, section, block, page, page_size)` and TTLs of 180 seconds for overview and 1800 seconds for capital/events. Store only in memory. Build local failure blocks with `provider=None`, `retryable`, and sanitized messages.

- [ ] **Step 4: Run service tests and verify GREEN**

Expected: all orchestration tests pass.

- [ ] **Step 5: Commit Task 3**

```bash
git add website/python-a/services/stock_research_service.py website/python-a/tests/test_stock_research_service.py
git commit -m "feat: orchestrate python-a stock research data"
```

## Task 4: HTTP Routes, AI Context, and Obsidian Snapshot

**Files:**
- Modify: `website/python-a/server.py`
- Create: `website/python-a/tests/test_stock_research_server.py`
- Modify: `website/python-a/tests/test_server_upload.py`

- [ ] **Step 1: Write failing route and snapshot tests**

Test route parsing independently from sockets:

```python
def test_parse_research_route(self):
    route = server.parse_research_route("/api/stocks/002580/research/events")
    self.assertEqual(route, ("002580", "events"))
```

Patch the global research service and test handler responses for success, invalid code, invalid `kind`, invalid pagination, and partial failures. Extend daily-review tests to assert the Markdown includes a concise “研究数据快照” section with provider and data date.

- [ ] **Step 2: Run route tests and verify RED**

Expected: missing route parser and snapshot integration failures.

- [ ] **Step 3: Add research service construction and GET routes**

Construct the service once at module scope with injectable Provider instances. Add handlers for the three paths and map the HTTP query `force=1` to the service argument `force=True`; also parse `kind`, `page`, and `page_size`. Map validation errors to HTTP 400 and unexpected orchestration errors to HTTP 502 with `{success:false,message}`.

- [ ] **Step 4: Integrate compact snapshots**

Before DeepSeek analysis, call `build_snapshot(code, load_missing=True)`, include it in the model context, and return it as `research_snapshot`. Accept `research_snapshot` in professional-report requests and daily-review saves. If a direct save has no snapshot, build one from current cache. Render only the compact snapshot in Markdown.

- [ ] **Step 5: Run server and regression tests**

Run:

```bash
cd website/python-a
python -m unittest tests.test_stock_research_server tests.test_server_upload -v
python -m unittest discover -s tests -v
```

Expected: all tests pass and no external process or network request starts.

- [ ] **Step 6: Commit Task 4**

```bash
git add website/python-a/server.py website/python-a/tests/test_stock_research_server.py website/python-a/tests/test_server_upload.py
git commit -m "feat: expose python-a stock research APIs"
```

## Task 5: Research Tabs and Lazy Loading UI

**Files:**
- Modify: `website/python-a/index.html`
- Modify: `website/python-a/app.js`
- Modify: `website/python-a/styles.css`

- [ ] **Step 1: Add static DOM structure**

Insert a segmented research tab control after `.analysis-grid` and before `.memory-panel-inline`. Add three fixed-height panels with semantic IDs:

```text
researchOverviewPanel
researchCapitalPanel
researchEventsPanel
```

Add source metadata elements per data block and independent report/announcement “加载更多” buttons.

- [ ] **Step 2: Implement frontend state and safe rendering**

Add state:

```javascript
state.research = {
  activeTab: "overview",
  byCode: {},
  aiSnapshot: null,
};
```

Implement `loadResearchSection`, `renderResearchSection`, `escapeHtml`, `safeExternalUrl`, and independent event pagination. Overview loads after stock selection; other sections load on first tab activation. Ignore stale responses if the selected stock changed during the request.

- [ ] **Step 3: Integrate refresh, AI, and save actions**

Top-level refresh must refresh watchlist and force-refresh the active research tab only. AI requests include the selected code and store returned `research_snapshot`. Professional-report and review-save payloads use the same snapshot until AI is generated again.

- [ ] **Step 4: Add restrained responsive styling**

Use the existing neutral/green visual system. Keep controls at 8px radius or less. Use compact metric grids, unframed data groups, fixed skeleton heights, wrapping concept chips, and two event columns on desktop that stack below 760px. Avoid nested decorative cards and preserve the current three-column workbench density.

- [ ] **Step 5: Run static checks**

```bash
node --check website/python-a/app.js
```

Expected: exit 0.

- [ ] **Step 6: Commit Task 5**

```bash
git add website/python-a/index.html website/python-a/app.js website/python-a/styles.css
git commit -m "feat: add python-a stock research tabs"
```

## Task 6: Documentation and End-to-End Verification

**Files:**
- Modify: `website/python-a/README.md`
- Modify: `website/python-a/AGENTS.md`
- Modify: `website/README.md`
- Modify: `website/AGENTS.md`
- Modify: `README.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: Update all required documentation**

Document the three APIs, query parameters, Provider fallback chains, truthful source metadata, standard-library dependency boundary, cache TTLs, AI/Obsidian snapshot behavior, and test commands. Preserve the independent Python microservice boundary and port 5174.

- [ ] **Step 2: Run complete automated verification**

```bash
cd website/python-a
python -m unittest discover -s tests -v
cd ../..
node --check website/python-a/app.js
```

Expected: all unittests pass and JavaScript syntax check exits 0.

- [ ] **Step 3: Start the service and smoke-test APIs**

Start `python server.py` from `website/python-a` on an unused port through `PORT`. Verify `/api/health`, the root page, and all three research routes. A third-party outage may produce block-level unavailable states but must not return malformed JSON or break the page.

- [ ] **Step 4: Run browser verification**

Use Playwright at desktop and mobile viewports. Verify overview auto-load, capital/events lazy load, source changes after fallback, report/announcement long-title wrapping, loading/empty/error states, no duplicate requests on tab switching, and no overlap. Capture screenshots and inspect them.

- [ ] **Step 5: Review repository changes and secrets**

Run `git diff --check`, inspect `git status --short`, and search changed files for API keys, tokens, `verify=False`, or disabled TLS verification. Do not stage existing unrelated untracked files.

- [ ] **Step 6: Commit documentation and verification updates**

```bash
git add AGENTS.md README.md website/AGENTS.md website/README.md website/python-a/AGENTS.md website/python-a/README.md
git commit -m "docs: document python-a stock research data"
```

## Final Acceptance

- [ ] Existing watchlist, chart, AI analysis, trading review, and Obsidian tests pass.
- [ ] Overview loads automatically; capital and events are lazy.
- [ ] Every successful data block displays its actual provider and timestamp.
- [ ] Mixed providers and partial failures render correctly.
- [ ] AI and Obsidian use the same compact research snapshot.
- [ ] Python 3.9-compatible syntax is used throughout.
- [ ] No `mootdx`, `pandas`, or `stockstats` runtime dependency is introduced.
- [ ] All six required documentation files match the implemented APIs.
