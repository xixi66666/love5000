# quant-a Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first professional vertical slice of `quant-a`: an independent FastAPI A-share multi-factor research service with mock data, DuckDB-backed storage, universe construction, Value-Quality-Momentum scoring, monthly backtest, report APIs, a workbench page, and `website` entry integration.

**Architecture:** Create `quant-a` as a Python microservice parallel to `python-a`, with focused modules under `quant-a/quant/`. The first release uses deterministic `mock_provider` data for tests and demos, keeps `eastmoney_provider` behind the same Provider interface, persists normalized research data through DuckDB/Parquet-ready repositories, and exposes service operations through FastAPI route modules.

**Tech Stack:** Python 3.9+, FastAPI, Uvicorn, Pydantic, DuckDB, pandas, PyYAML, requests, pytest, plain HTML/CSS/JavaScript.

---

## Scope Notes

This plan implements the first vertical closed loop from the approved spec:

- Independent `quant-a` service on port `5175`.
- Deterministic mock Provider for repeatable tests and local demo.
- Provider interface prepared for Eastmoney and later Tushare Pro.
- DuckDB storage and data version records.
- Index universe construction.
- Value-Quality-Momentum baseline scoring.
- Monthly rebalance backtest with basic cost, limit-up, limit-down, and suspension handling.
- Experiment record and report output.
- FastAPI endpoints and a direct workbench page.
- `website` homepage service card and `scripts/start-love5000.ps1` optional startup support.

The first implementation does not fetch production-grade full-market data. It builds the stable system boundary and a deterministic baseline that can be expanded safely.

## File Structure Map

Create:

- `quant-a/README.md` - service overview, run commands, API summary, investment-language boundary.
- `quant-a/requirements.txt` - runtime and test dependencies.
- `quant-a/main.py` - FastAPI app factory, static workbench mounting, router registration.
- `quant-a/configs/app.yaml` - default app, storage, provider, and model paths.
- `quant-a/configs/universe.yaml` - first index universe config.
- `quant-a/configs/model_v0_1.yaml` - VQM weights and factor settings.
- `quant-a/configs/cost_model.yaml` - commission, tax, slippage config.
- `quant-a/quant/common/response.py` - unified API response helpers.
- `quant-a/quant/common/config.py` - YAML config loader and typed config objects.
- `quant-a/quant/providers/base.py` - Provider protocol and domain data models.
- `quant-a/quant/providers/mock_provider.py` - deterministic market, financial, valuation, calendar, and index data.
- `quant-a/quant/providers/eastmoney_provider.py` - skeleton public market data adapter through the Provider interface.
- `quant-a/quant/storage/repository.py` - DuckDB schema initialization, upsert/write/read helpers.
- `quant-a/quant/calendar/service.py` - trading-day lookup and next-trade-day/month-end utilities.
- `quant-a/quant/universe/service.py` - universe filtering from index members and normalized data.
- `quant-a/quant/factors/engine.py` - factor calculation, ranking, missing data flags, risk penalties.
- `quant-a/quant/scoring/service.py` - VQM score composition and ranking.
- `quant-a/quant/portfolio/service.py` - target portfolio generation with weight limits.
- `quant-a/quant/backtest/service.py` - monthly backtest, order simulation, NAV calculation.
- `quant-a/quant/risk/service.py` - bias disclosure and risk flag aggregation.
- `quant-a/quant/experiments/service.py` - experiment IDs and persisted run metadata.
- `quant-a/quant/reports/service.py` - report assembly from scores, backtest, orders, holdings.
- `quant-a/quant/services/pipeline.py` - orchestration methods called by API routes.
- `quant-a/quant/api/routes.py` - FastAPI endpoints.
- `quant-a/web/index.html` - workbench shell.
- `quant-a/web/app.js` - API calls and workbench rendering.
- `quant-a/web/styles.css` - workbench styling.
- `quant-a/tests/test_health.py` - app health and response contract tests.
- `quant-a/tests/test_provider_storage.py` - mock provider and storage tests.
- `quant-a/tests/test_calendar_universe.py` - trading calendar and universe tests.
- `quant-a/tests/test_scoring.py` - factor and VQM score tests.
- `quant-a/tests/test_backtest.py` - monthly backtest and order handling tests.
- `quant-a/tests/test_api_pipeline.py` - API pipeline integration tests.

Modify:

- `website/src/main/resources/static/index.html` - add `Quant · 5175` nav/service entry.
- `website/src/main/resources/static/css/style.css` - add `service-card-quant` color hook if needed.
- `scripts/start-love5000.ps1` - add optional `-StartQuant` and `-QuantPort` startup path.
- `AGENTS.md` - document `quant-a` module, commands, port, and boundary.

Do not modify:

- `python-a/server.py`
- `python-a/app.js`
- `pom.xml`
- any `target/` directory

---

### Task 1: Scaffold `quant-a` Service Skeleton

**Files:**
- Create: `quant-a/requirements.txt`
- Create: `quant-a/main.py`
- Create: `quant-a/quant/common/response.py`
- Create: `quant-a/quant/api/routes.py`
- Create: `quant-a/web/index.html`
- Create: `quant-a/tests/test_health.py`

- [ ] **Step 1: Write the failing health/API contract test**

Create `quant-a/tests/test_health.py`:

```python
from fastapi.testclient import TestClient

from main import app


def test_health_returns_success_payload():
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {
            "service": "quant-a",
            "status": "ok",
            "port": 5175,
        },
        "message": "",
    }


def test_workbench_page_is_served():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "quant-a" in response.text
    assert "多因子量化研究工作台" in response.text
```

- [ ] **Step 2: Run the health test and confirm it fails because the service does not exist**

Run:

```powershell
cd quant-a
python -m pytest tests/test_health.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'main'
```

- [ ] **Step 3: Add dependencies**

Create `quant-a/requirements.txt`:

```text
fastapi
uvicorn
pydantic
duckdb
pandas
pyyaml
requests
pytest
httpx
```

- [ ] **Step 4: Implement unified response helpers**

Create `quant-a/quant/common/response.py`:

```python
from typing import Any, Dict


def success(data: Any = None, message: str = "") -> Dict[str, Any]:
    return {
        "success": True,
        "data": {} if data is None else data,
        "message": message,
    }


def failure(message: str) -> Dict[str, Any]:
    return {
        "success": False,
        "message": message,
    }
```

- [ ] **Step 5: Implement API routes**

Create `quant-a/quant/api/routes.py`:

```python
from fastapi import APIRouter

from quant.common.response import success

router = APIRouter(prefix="/api")


@router.get("/health")
def health():
    return success({
        "service": "quant-a",
        "status": "ok",
        "port": 5175,
    })
```

- [ ] **Step 6: Implement the initial workbench page**

Create `quant-a/web/index.html`:

```html
<!doctype html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>quant-a 多因子量化研究工作台</title>
</head>
<body>
    <main>
        <h1>quant-a 多因子量化研究工作台</h1>
        <p>专业 A 股多因子研究、评分、回测和风险披露。</p>
    </main>
</body>
</html>
```

- [ ] **Step 7: Implement FastAPI app mounting**

Create `quant-a/main.py`:

```python
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from quant.api.routes import router

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"

app = FastAPI(title="quant-a", version="0.1.0")
app.include_router(router)


@app.get("/", response_class=HTMLResponse)
def workbench():
    return (WEB_DIR / "index.html").read_text(encoding="utf-8")
```

- [ ] **Step 8: Run the health test and confirm it passes**

Run:

```powershell
cd quant-a
python -m pytest tests/test_health.py -v
```

Expected:

```text
2 passed
```

- [ ] **Step 9: Commit the service skeleton**

```powershell
git add quant-a/requirements.txt quant-a/main.py quant-a/quant/common/response.py quant-a/quant/api/routes.py quant-a/web/index.html quant-a/tests/test_health.py
git commit -m "feat: scaffold quant-a service"
```

---

### Task 2: Add Config Loading and App Defaults

**Files:**
- Create: `quant-a/configs/app.yaml`
- Create: `quant-a/configs/universe.yaml`
- Create: `quant-a/configs/model_v0_1.yaml`
- Create: `quant-a/configs/cost_model.yaml`
- Create: `quant-a/quant/common/config.py`
- Modify: `quant-a/quant/api/routes.py`
- Test: `quant-a/tests/test_health.py`

- [ ] **Step 1: Extend the status test**

Append to `quant-a/tests/test_health.py`:

```python
def test_status_exposes_configured_versions():
    client = TestClient(app)

    response = client.get("/api/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["service"] == "quant-a"
    assert payload["data"]["model_version"] == "v0.1"
    assert payload["data"]["provider"] == "mock"
    assert payload["data"]["storage"]["duckdb_path"].endswith("data/quant.duckdb")
```

- [ ] **Step 2: Run the status test and confirm it fails**

Run:

```powershell
cd quant-a
python -m pytest tests/test_health.py::test_status_exposes_configured_versions -v
```

Expected:

```text
404 Not Found
```

- [ ] **Step 3: Add app config**

Create `quant-a/configs/app.yaml`:

```yaml
app:
  name: quant-a
  host: 127.0.0.1
  port: 5175
provider:
  active: mock
storage:
  duckdb_path: data/quant.duckdb
  parquet_root: data
versions:
  model_version: v0.1
  config_version: app-v0.1
```

- [ ] **Step 4: Add universe config**

Create `quant-a/configs/universe.yaml`:

```yaml
universe:
  type: index_members
  indexes:
    - CSI300
    - CSI500
  filters:
    include_st: false
    min_listed_days: 120
    min_avg_amount_20d: 50000000
    exclude_suspended: true
```

- [ ] **Step 5: Add model config**

Create `quant-a/configs/model_v0_1.yaml`:

```yaml
model:
  name: Value-Quality-Momentum
  version: v0.1
  weights:
    value: 0.30
    quality: 0.35
    momentum: 0.25
  risk_penalty:
    max_points: 10.0
  top_n: 30
  industry_weight_limit: 0.30
  single_stock_weight_limit: 0.05
```

- [ ] **Step 6: Add cost model config**

Create `quant-a/configs/cost_model.yaml`:

```yaml
cost_model:
  version: cn-a-v0.1
  commission_rate: 0.00025
  min_commission: 5.0
  stamp_tax_rate: 0.0005
  transfer_fee_rate: 0.00001
  slippage_bps: 10
```

- [ ] **Step 7: Implement config loader**

Create `quant-a/quant/common/config.py`:

```python
from pathlib import Path
from typing import Any, Dict

import yaml

BASE_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = BASE_DIR / "configs"


def load_yaml(name: str) -> Dict[str, Any]:
    path = CONFIG_DIR / name
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_app_config() -> Dict[str, Any]:
    return load_yaml("app.yaml")


def load_universe_config() -> Dict[str, Any]:
    return load_yaml("universe.yaml")


def load_model_config() -> Dict[str, Any]:
    return load_yaml("model_v0_1.yaml")


def load_cost_config() -> Dict[str, Any]:
    return load_yaml("cost_model.yaml")
```

- [ ] **Step 8: Add `/api/status` route**

Modify `quant-a/quant/api/routes.py` to:

```python
from fastapi import APIRouter

from quant.common.config import load_app_config
from quant.common.response import success

router = APIRouter(prefix="/api")


@router.get("/health")
def health():
    return success({
        "service": "quant-a",
        "status": "ok",
        "port": 5175,
    })


@router.get("/status")
def status():
    config = load_app_config()
    return success({
        "service": config["app"]["name"],
        "provider": config["provider"]["active"],
        "model_version": config["versions"]["model_version"],
        "config_version": config["versions"]["config_version"],
        "storage": config["storage"],
    })
```

- [ ] **Step 9: Run status tests**

Run:

```powershell
cd quant-a
python -m pytest tests/test_health.py -v
```

Expected:

```text
3 passed
```

- [ ] **Step 10: Commit config loading**

```powershell
git add quant-a/configs quant-a/quant/common/config.py quant-a/quant/api/routes.py quant-a/tests/test_health.py
git commit -m "feat: add quant-a configuration"
```

---

### Task 3: Implement Provider Models and Deterministic Mock Data

**Files:**
- Create: `quant-a/quant/providers/base.py`
- Create: `quant-a/quant/providers/mock_provider.py`
- Create: `quant-a/quant/providers/eastmoney_provider.py`
- Create: `quant-a/tests/test_provider_storage.py`

- [ ] **Step 1: Write provider contract tests**

Create `quant-a/tests/test_provider_storage.py`:

```python
from quant.providers.mock_provider import MockProvider


def test_mock_provider_returns_trade_calendar():
    provider = MockProvider()

    calendar = provider.get_trade_calendar("2024-01-01", "2024-03-31")

    assert len(calendar) >= 40
    assert calendar[0].trade_date == "2024-01-02"
    assert calendar[0].is_open is True
    assert calendar[-1].next_trade_date is None


def test_mock_provider_returns_index_members_and_daily_bars():
    provider = MockProvider()

    members = provider.get_index_members(["CSI300"], "2024-01-31")
    bars = provider.get_daily_bars("2024-01-02", "2024-03-31")

    assert {member.index_code for member in members} == {"CSI300"}
    assert len(members) == 6
    assert any(bar.code == "600001" and bar.trade_date == "2024-01-02" for bar in bars)
    assert all(bar.available_date > bar.trade_date for bar in bars)


def test_mock_provider_returns_financial_and_valuation_data():
    provider = MockProvider()

    financials = provider.get_financials()
    valuations = provider.get_valuation("2024-01-02", "2024-03-31")

    assert any(item.code == "600001" and item.roe > 0 for item in financials)
    assert any(item.code == "600001" and item.pb > 0 for item in valuations)
```

- [ ] **Step 2: Run provider tests and confirm imports fail**

Run:

```powershell
cd quant-a
python -m pytest tests/test_provider_storage.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'quant.providers'
```

- [ ] **Step 3: Implement provider data models and protocol**

Create `quant-a/quant/providers/base.py`:

```python
from dataclasses import dataclass
from typing import List, Optional, Protocol


@dataclass(frozen=True)
class TradeCalendarRow:
    trade_date: str
    is_open: bool
    prev_trade_date: Optional[str]
    next_trade_date: Optional[str]
    is_month_end: bool


@dataclass(frozen=True)
class StockBasicRow:
    code: str
    name: str
    exchange: str
    list_date: str
    delist_date: Optional[str]
    status: str
    industry: str
    is_st: bool


@dataclass(frozen=True)
class DailyBarRow:
    trade_date: str
    code: str
    open: float
    high: float
    low: float
    close: float
    pre_close: float
    volume: float
    amount: float
    turnover_rate: float
    adj_factor: float
    limit_up: float
    limit_down: float
    suspend_flag: bool
    available_date: str
    data_version: str


@dataclass(frozen=True)
class ValuationRow:
    trade_date: str
    code: str
    pe_ttm: float
    pb: float
    ps_ttm: float
    pcf_ttm: float
    dividend_yield: float
    total_market_value: float
    float_market_value: float
    available_date: str
    data_version: str


@dataclass(frozen=True)
class FinancialRow:
    code: str
    report_period: str
    announce_date: str
    available_date: str
    revenue: float
    net_profit: float
    deducted_net_profit: float
    operating_cash_flow: float
    roe: float
    roa: float
    gross_margin: float
    net_margin: float
    debt_ratio: float
    data_version: str


@dataclass(frozen=True)
class IndexMemberRow:
    index_code: str
    code: str
    effective_date: str
    expire_date: Optional[str]
    data_version: str


class DataProvider(Protocol):
    def get_trade_calendar(self, start_date: str, end_date: str) -> List[TradeCalendarRow]:
        raise NotImplementedError

    def get_stock_basic(self) -> List[StockBasicRow]:
        raise NotImplementedError

    def get_daily_bars(self, start_date: str, end_date: str) -> List[DailyBarRow]:
        raise NotImplementedError

    def get_valuation(self, start_date: str, end_date: str) -> List[ValuationRow]:
        raise NotImplementedError

    def get_financials(self) -> List[FinancialRow]:
        raise NotImplementedError

    def get_index_members(self, index_codes: List[str], trade_date: str) -> List[IndexMemberRow]:
        raise NotImplementedError
```

- [ ] **Step 4: Implement deterministic mock provider**

Create `quant-a/quant/providers/mock_provider.py`:

```python
from datetime import date, timedelta
from typing import List

from quant.providers.base import (
    DailyBarRow,
    FinancialRow,
    IndexMemberRow,
    StockBasicRow,
    TradeCalendarRow,
    ValuationRow,
)


class MockProvider:
    data_version = "mock-2024-q1"

    codes = [
        ("600001", "浦江制造", "SH", "2010-01-01", "工业", False),
        ("600002", "海岳能源", "SH", "2012-05-10", "能源", False),
        ("600003", "星河科技", "SH", "2016-03-18", "科技", False),
        ("000001", "南方银行", "SZ", "1991-04-03", "金融", False),
        ("000002", "长风地产", "SZ", "2001-09-21", "地产", False),
        ("000003", "华康医药", "SZ", "2018-07-11", "医药", False),
    ]

    def get_trade_calendar(self, start_date: str, end_date: str) -> List[TradeCalendarRow]:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        days = []
        current = start
        while current <= end:
            if current.weekday() < 5:
                days.append(current.isoformat())
            current += timedelta(days=1)

        rows = []
        for index, day in enumerate(days):
            next_day = days[index + 1] if index + 1 < len(days) else None
            rows.append(TradeCalendarRow(
                trade_date=day,
                is_open=True,
                prev_trade_date=days[index - 1] if index > 0 else None,
                next_trade_date=next_day,
                is_month_end=next_day is None or next_day[:7] != day[:7],
            ))
        return rows

    def get_stock_basic(self) -> List[StockBasicRow]:
        return [
            StockBasicRow(code, name, exchange, list_date, None, "listed", industry, is_st)
            for code, name, exchange, list_date, industry, is_st in self.codes
        ]

    def get_index_members(self, index_codes: List[str], trade_date: str) -> List[IndexMemberRow]:
        rows = []
        for index_code in index_codes:
            for code, *_ in self.codes:
                rows.append(IndexMemberRow(index_code, code, "2024-01-01", None, self.data_version))
        return rows

    def get_daily_bars(self, start_date: str, end_date: str) -> List[DailyBarRow]:
        calendar = self.get_trade_calendar(start_date, end_date)
        rows = []
        for code_index, (code, *_rest) in enumerate(self.codes):
            base = 10.0 + code_index * 3
            for day_index, cal in enumerate(calendar):
                close = round(base + day_index * (0.05 + code_index * 0.01), 2)
                pre_close = round(close - 0.05, 2)
                rows.append(DailyBarRow(
                    trade_date=cal.trade_date,
                    code=code,
                    open=round(close - 0.02, 2),
                    high=round(close + 0.15, 2),
                    low=round(close - 0.20, 2),
                    close=close,
                    pre_close=pre_close,
                    volume=1000000 + code_index * 100000,
                    amount=(1000000 + code_index * 100000) * close,
                    turnover_rate=1.5 + code_index * 0.2,
                    adj_factor=1.0,
                    limit_up=round(pre_close * 1.1, 2),
                    limit_down=round(pre_close * 0.9, 2),
                    suspend_flag=False,
                    available_date=cal.next_trade_date or cal.trade_date,
                    data_version=self.data_version,
                ))
        return rows

    def get_valuation(self, start_date: str, end_date: str) -> List[ValuationRow]:
        calendar = self.get_trade_calendar(start_date, end_date)
        rows = []
        for code_index, (code, *_rest) in enumerate(self.codes):
            for cal in calendar:
                rows.append(ValuationRow(
                    trade_date=cal.trade_date,
                    code=code,
                    pe_ttm=12.0 + code_index * 2,
                    pb=1.1 + code_index * 0.2,
                    ps_ttm=1.8 + code_index * 0.3,
                    pcf_ttm=9.0 + code_index,
                    dividend_yield=0.01 + code_index * 0.002,
                    total_market_value=20000000000 + code_index * 3000000000,
                    float_market_value=15000000000 + code_index * 2500000000,
                    available_date=cal.next_trade_date or cal.trade_date,
                    data_version=self.data_version,
                ))
        return rows

    def get_financials(self) -> List[FinancialRow]:
        rows = []
        for code_index, (code, *_rest) in enumerate(self.codes):
            rows.append(FinancialRow(
                code=code,
                report_period="2023-12-31",
                announce_date="2024-01-15",
                available_date="2024-01-16",
                revenue=1000000000 + code_index * 90000000,
                net_profit=120000000 + code_index * 10000000,
                deducted_net_profit=110000000 + code_index * 9000000,
                operating_cash_flow=140000000 + code_index * 8000000,
                roe=0.08 + code_index * 0.015,
                roa=0.04 + code_index * 0.006,
                gross_margin=0.25 + code_index * 0.02,
                net_margin=0.12 + code_index * 0.01,
                debt_ratio=0.55 - code_index * 0.03,
                data_version=self.data_version,
            ))
        return rows
```

- [ ] **Step 5: Add Eastmoney provider boundary**

Create `quant-a/quant/providers/eastmoney_provider.py`:

```python
from typing import List

import requests

from quant.providers.base import DailyBarRow, DataProvider


class EastmoneyProvider:
    def __init__(self, timeout_seconds: int = 10):
        self.timeout_seconds = timeout_seconds

    def _get_json(self, url: str, params: dict) -> dict:
        response = requests.get(url, params=params, timeout=self.timeout_seconds)
        response.raise_for_status()
        return response.json()

    def get_daily_bars(self, start_date: str, end_date: str) -> List[DailyBarRow]:
        raise NotImplementedError("Eastmoney daily bar parsing is implemented after mock pipeline is stable.")
```

- [ ] **Step 6: Run provider tests**

Run:

```powershell
cd quant-a
python -m pytest tests/test_provider_storage.py -v
```

Expected:

```text
3 passed
```

- [ ] **Step 7: Commit provider layer**

```powershell
git add quant-a/quant/providers quant-a/tests/test_provider_storage.py
git commit -m "feat: add quant-a provider contracts"
```

---

### Task 4: Add DuckDB Repository and Data Sync Pipeline

**Files:**
- Create: `quant-a/quant/storage/repository.py`
- Create: `quant-a/quant/services/pipeline.py`
- Modify: `quant-a/tests/test_provider_storage.py`

- [ ] **Step 1: Add storage tests**

Append to `quant-a/tests/test_provider_storage.py`:

```python
from pathlib import Path

from quant.services.pipeline import QuantPipeline
from quant.storage.repository import QuantRepository


def test_repository_syncs_mock_data(tmp_path: Path):
    db_path = tmp_path / "quant.duckdb"
    repository = QuantRepository(db_path)
    pipeline = QuantPipeline(repository=repository, provider=MockProvider())

    result = pipeline.sync_data("2024-01-02", "2024-03-31", ["CSI300"])

    assert result["data_version"] == "mock-2024-q1"
    assert result["stock_count"] == 6
    assert result["daily_bar_count"] > 200
    assert repository.count_rows("stock_basic") == 6
    assert repository.count_rows("daily_bar") == result["daily_bar_count"]
    assert repository.latest_data_version() == "mock-2024-q1"
```

- [ ] **Step 2: Run storage test and confirm it fails**

Run:

```powershell
cd quant-a
python -m pytest tests/test_provider_storage.py::test_repository_syncs_mock_data -v
```

Expected:

```text
ModuleNotFoundError: No module named 'quant.services'
```

- [ ] **Step 3: Implement DuckDB repository**

Create `quant-a/quant/storage/repository.py`:

```python
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Iterable, List, Mapping

import duckdb


class QuantRepository:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = duckdb.connect(str(self.db_path))
        self.initialize_schema()

    def initialize_schema(self) -> None:
        self.connection.execute("""
            create table if not exists data_versions (
                data_version varchar primary key,
                provider varchar,
                start_date varchar,
                end_date varchar,
                created_at timestamp default current_timestamp
            )
        """)
        self.connection.execute("create table if not exists stock_basic as select * from (select '' code, '' name, '' exchange, '' list_date, null::varchar delist_date, '' status, '' industry, false is_st) where false")
        self.connection.execute("create table if not exists trade_calendar as select * from (select '' trade_date, true is_open, null::varchar prev_trade_date, null::varchar next_trade_date, false is_month_end) where false")
        self.connection.execute("create table if not exists daily_bar as select * from (select '' trade_date, '' code, 0.0 open, 0.0 high, 0.0 low, 0.0 close, 0.0 pre_close, 0.0 volume, 0.0 amount, 0.0 turnover_rate, 0.0 adj_factor, 0.0 limit_up, 0.0 limit_down, false suspend_flag, '' available_date, '' data_version) where false")
        self.connection.execute("create table if not exists valuation as select * from (select '' trade_date, '' code, 0.0 pe_ttm, 0.0 pb, 0.0 ps_ttm, 0.0 pcf_ttm, 0.0 dividend_yield, 0.0 total_market_value, 0.0 float_market_value, '' available_date, '' data_version) where false")
        self.connection.execute("create table if not exists financial as select * from (select '' code, '' report_period, '' announce_date, '' available_date, 0.0 revenue, 0.0 net_profit, 0.0 deducted_net_profit, 0.0 operating_cash_flow, 0.0 roe, 0.0 roa, 0.0 gross_margin, 0.0 net_margin, 0.0 debt_ratio, '' data_version) where false")
        self.connection.execute("create table if not exists index_member as select * from (select '' index_code, '' code, '' effective_date, null::varchar expire_date, '' data_version) where false")

    def replace_table(self, table: str, rows: Iterable[object]) -> int:
        items = [asdict(row) if is_dataclass(row) else dict(row) for row in rows]
        self.connection.execute(f"delete from {table}")
        if not items:
            return 0
        columns = list(items[0].keys())
        placeholders = ", ".join(["?"] * len(columns))
        column_sql = ", ".join(columns)
        values = [tuple(item[column] for column in columns) for item in items]
        self.connection.executemany(f"insert into {table} ({column_sql}) values ({placeholders})", values)
        return len(items)

    def record_data_version(self, data_version: str, provider: str, start_date: str, end_date: str) -> None:
        self.connection.execute(
            "insert or replace into data_versions (data_version, provider, start_date, end_date) values (?, ?, ?, ?)",
            [data_version, provider, start_date, end_date],
        )

    def count_rows(self, table: str) -> int:
        return self.connection.execute(f"select count(*) from {table}").fetchone()[0]

    def latest_data_version(self) -> str:
        row = self.connection.execute("select data_version from data_versions order by created_at desc limit 1").fetchone()
        return row[0] if row else ""

    def fetch_dicts(self, query: str, params: List[object] = None) -> List[Mapping[str, object]]:
        cursor = self.connection.execute(query, params or [])
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
```

- [ ] **Step 4: Implement pipeline sync**

Create `quant-a/quant/services/pipeline.py`:

```python
from pathlib import Path
from typing import Dict, List, Optional

from quant.providers.mock_provider import MockProvider
from quant.storage.repository import QuantRepository


class QuantPipeline:
    def __init__(self, repository: Optional[QuantRepository] = None, provider: Optional[MockProvider] = None):
        self.repository = repository or QuantRepository(Path("data/quant.duckdb"))
        self.provider = provider or MockProvider()

    def sync_data(self, start_date: str, end_date: str, index_codes: List[str]) -> Dict[str, object]:
        calendar = self.provider.get_trade_calendar(start_date, end_date)
        stocks = self.provider.get_stock_basic()
        daily_bars = self.provider.get_daily_bars(start_date, end_date)
        valuations = self.provider.get_valuation(start_date, end_date)
        financials = self.provider.get_financials()
        members = self.provider.get_index_members(index_codes, end_date)
        data_version = self.provider.data_version

        counts = {
            "calendar_count": self.repository.replace_table("trade_calendar", calendar),
            "stock_count": self.repository.replace_table("stock_basic", stocks),
            "daily_bar_count": self.repository.replace_table("daily_bar", daily_bars),
            "valuation_count": self.repository.replace_table("valuation", valuations),
            "financial_count": self.repository.replace_table("financial", financials),
            "index_member_count": self.repository.replace_table("index_member", members),
        }
        self.repository.record_data_version(data_version, "mock", start_date, end_date)
        return {
            "data_version": data_version,
            **counts,
        }
```

- [ ] **Step 5: Run provider and storage tests**

Run:

```powershell
cd quant-a
python -m pytest tests/test_provider_storage.py -v
```

Expected:

```text
4 passed
```

- [ ] **Step 6: Commit storage and pipeline sync**

```powershell
git add quant-a/quant/storage/repository.py quant-a/quant/services/pipeline.py quant-a/tests/test_provider_storage.py
git commit -m "feat: persist quant-a mock data"
```

---

### Task 5: Implement Calendar and Universe Services

**Files:**
- Create: `quant-a/quant/calendar/service.py`
- Create: `quant-a/quant/universe/service.py`
- Create: `quant-a/tests/test_calendar_universe.py`

- [ ] **Step 1: Write calendar and universe tests**

Create `quant-a/tests/test_calendar_universe.py`:

```python
from pathlib import Path

from quant.calendar.service import TradingCalendarService
from quant.providers.mock_provider import MockProvider
from quant.services.pipeline import QuantPipeline
from quant.storage.repository import QuantRepository
from quant.universe.service import UniverseService


def build_repository(tmp_path: Path) -> QuantRepository:
    repository = QuantRepository(tmp_path / "quant.duckdb")
    QuantPipeline(repository=repository, provider=MockProvider()).sync_data("2024-01-02", "2024-03-31", ["CSI300"])
    return repository


def test_calendar_returns_next_trade_day_and_month_ends(tmp_path):
    repository = build_repository(tmp_path)
    service = TradingCalendarService(repository)

    assert service.next_trade_date("2024-01-31") == "2024-02-01"
    assert "2024-01-31" in service.month_end_trade_dates("2024-01-02", "2024-03-31")
    assert "2024-02-29" in service.month_end_trade_dates("2024-01-02", "2024-03-31")


def test_universe_builds_filtered_index_pool(tmp_path):
    repository = build_repository(tmp_path)
    service = UniverseService(repository)

    universe = service.build_universe(
        trade_date="2024-01-31",
        index_codes=["CSI300"],
        min_listed_days=120,
        min_avg_amount_20d=50000000,
        include_st=False,
        exclude_suspended=True,
    )

    assert len(universe) == 6
    assert universe[0]["code"] == "600001"
    assert all(item["avg_amount_20d"] >= 50000000 for item in universe)
```

- [ ] **Step 2: Run tests and confirm imports fail**

Run:

```powershell
cd quant-a
python -m pytest tests/test_calendar_universe.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'quant.calendar'
```

- [ ] **Step 3: Implement calendar service**

Create `quant-a/quant/calendar/service.py`:

```python
from typing import List

from quant.storage.repository import QuantRepository


class TradingCalendarService:
    def __init__(self, repository: QuantRepository):
        self.repository = repository

    def next_trade_date(self, trade_date: str) -> str:
        rows = self.repository.fetch_dicts(
            "select next_trade_date from trade_calendar where trade_date = ?",
            [trade_date],
        )
        if not rows or not rows[0]["next_trade_date"]:
            raise ValueError(f"No next trade date for {trade_date}")
        return str(rows[0]["next_trade_date"])

    def month_end_trade_dates(self, start_date: str, end_date: str) -> List[str]:
        rows = self.repository.fetch_dicts(
            """
            select trade_date
            from trade_calendar
            where trade_date between ? and ?
              and is_month_end = true
            order by trade_date
            """,
            [start_date, end_date],
        )
        return [str(row["trade_date"]) for row in rows]
```

- [ ] **Step 4: Implement universe service**

Create `quant-a/quant/universe/service.py`:

```python
from datetime import date
from typing import Dict, List

from quant.storage.repository import QuantRepository


class UniverseService:
    def __init__(self, repository: QuantRepository):
        self.repository = repository

    def build_universe(
        self,
        trade_date: str,
        index_codes: List[str],
        min_listed_days: int,
        min_avg_amount_20d: float,
        include_st: bool,
        exclude_suspended: bool,
    ) -> List[Dict[str, object]]:
        rows = self.repository.fetch_dicts(
            """
            with member_pool as (
                select distinct code
                from index_member
                where index_code in ({placeholders})
                  and effective_date <= ?
                  and (expire_date is null or expire_date > ?)
            ),
            amount_20d as (
                select code, avg(amount) as avg_amount_20d
                from (
                    select code, amount,
                           row_number() over (partition by code order by trade_date desc) as rn
                    from daily_bar
                    where trade_date <= ?
                )
                where rn <= 20
                group by code
            ),
            latest_bar as (
                select code, suspend_flag
                from daily_bar
                where trade_date = ?
            )
            select s.code, s.name, s.exchange, s.list_date, s.industry, s.is_st,
                   coalesce(a.avg_amount_20d, 0) as avg_amount_20d,
                   coalesce(b.suspend_flag, false) as suspend_flag
            from stock_basic s
            join member_pool m on s.code = m.code
            left join amount_20d a on s.code = a.code
            left join latest_bar b on s.code = b.code
            order by s.code
            """.format(placeholders=", ".join(["?"] * len(index_codes))),
            [*index_codes, trade_date, trade_date, trade_date, trade_date],
        )
        trade_day = date.fromisoformat(trade_date)
        result = []
        for row in rows:
            listed_days = (trade_day - date.fromisoformat(str(row["list_date"]))).days
            if listed_days < min_listed_days:
                continue
            if not include_st and row["is_st"]:
                continue
            if exclude_suspended and row["suspend_flag"]:
                continue
            if float(row["avg_amount_20d"]) < min_avg_amount_20d:
                continue
            result.append({
                **row,
                "listed_days": listed_days,
            })
        return result
```

- [ ] **Step 5: Run calendar and universe tests**

Run:

```powershell
cd quant-a
python -m pytest tests/test_calendar_universe.py -v
```

Expected:

```text
2 passed
```

- [ ] **Step 6: Commit calendar and universe**

```powershell
git add quant-a/quant/calendar/service.py quant-a/quant/universe/service.py quant-a/tests/test_calendar_universe.py
git commit -m "feat: build quant-a index universe"
```

---

### Task 6: Implement Factors and Value-Quality-Momentum Scoring

**Files:**
- Create: `quant-a/quant/factors/engine.py`
- Create: `quant-a/quant/scoring/service.py`
- Create: `quant-a/tests/test_scoring.py`

- [ ] **Step 1: Write scoring tests**

Create `quant-a/tests/test_scoring.py`:

```python
from pathlib import Path

from quant.factors.engine import FactorEngine
from quant.providers.mock_provider import MockProvider
from quant.scoring.service import ScoringService
from quant.services.pipeline import QuantPipeline
from quant.storage.repository import QuantRepository
from quant.universe.service import UniverseService


def build_repository(tmp_path: Path) -> QuantRepository:
    repository = QuantRepository(tmp_path / "quant.duckdb")
    QuantPipeline(repository=repository, provider=MockProvider()).sync_data("2024-01-02", "2024-03-31", ["CSI300"])
    return repository


def test_factor_engine_calculates_vqm_factors(tmp_path):
    repository = build_repository(tmp_path)
    universe = UniverseService(repository).build_universe("2024-03-29", ["CSI300"], 120, 50000000, False, True)
    factors = FactorEngine(repository).calculate("2024-03-29", universe)

    assert len(factors) == 6
    first = factors[0]
    assert first["code"] == "600001"
    assert "pb_inverse" in first["factor_raw_values"]
    assert "return_60d_exclude_5d" in first["factor_raw_values"]
    assert 0 <= first["value_score"] <= 100
    assert 0 <= first["quality_score"] <= 100
    assert 0 <= first["momentum_score"] <= 100


def test_scoring_service_ranks_total_score(tmp_path):
    repository = build_repository(tmp_path)
    universe = UniverseService(repository).build_universe("2024-03-29", ["CSI300"], 120, 50000000, False, True)
    factors = FactorEngine(repository).calculate("2024-03-29", universe)
    scores = ScoringService().score("2024-03-29", factors, "mock-2024-q1", "v0.1")

    assert len(scores) == 6
    assert scores[0]["rank"] == 1
    assert scores[0]["total_score"] >= scores[-1]["total_score"]
    assert scores[0]["model_version"] == "v0.1"
```

- [ ] **Step 2: Run scoring tests and confirm imports fail**

Run:

```powershell
cd quant-a
python -m pytest tests/test_scoring.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'quant.factors'
```

- [ ] **Step 3: Implement factor engine**

Create `quant-a/quant/factors/engine.py`:

```python
from typing import Dict, List

from quant.storage.repository import QuantRepository


def rank_percentile(values: List[float], higher_is_better: bool = True) -> List[float]:
    indexed = list(enumerate(values))
    indexed.sort(key=lambda item: item[1], reverse=higher_is_better)
    if len(indexed) == 1:
        return [100.0]
    scores = [0.0] * len(indexed)
    for rank, (index, _value) in enumerate(indexed):
        scores[index] = round(100.0 * (len(indexed) - rank - 1) / (len(indexed) - 1), 4)
    return scores


class FactorEngine:
    def __init__(self, repository: QuantRepository):
        self.repository = repository

    def calculate(self, trade_date: str, universe: List[Dict[str, object]]) -> List[Dict[str, object]]:
        codes = [item["code"] for item in universe]
        if not codes:
            return []
        placeholders = ", ".join(["?"] * len(codes))
        valuations = {
            row["code"]: row
            for row in self.repository.fetch_dicts(
                f"select * from valuation where trade_date = ? and code in ({placeholders})",
                [trade_date, *codes],
            )
        }
        financials = {
            row["code"]: row
            for row in self.repository.fetch_dicts(
                f"select * from financial where code in ({placeholders})",
                codes,
            )
        }
        returns = self._momentum_returns(trade_date, codes)

        raw_rows = []
        for stock in universe:
            code = str(stock["code"])
            valuation = valuations[code]
            financial = financials[code]
            raw = {
                "pb_inverse": 1.0 / max(float(valuation["pb"]), 0.01),
                "pe_ttm_inverse": 1.0 / max(float(valuation["pe_ttm"]), 0.01),
                "ps_ttm_inverse": 1.0 / max(float(valuation["ps_ttm"]), 0.01),
                "roe": float(financial["roe"]),
                "operating_cash_flow_to_profit": float(financial["operating_cash_flow"]) / max(float(financial["net_profit"]), 1.0),
                "gross_margin": float(financial["gross_margin"]),
                "debt_ratio_inverse": 1.0 - float(financial["debt_ratio"]),
                "return_60d_exclude_5d": returns[code]["return_60d_exclude_5d"],
                "return_120d_exclude_5d": returns[code]["return_120d_exclude_5d"],
                "ma_trend_score": returns[code]["ma_trend_score"],
            }
            raw_rows.append({
                **stock,
                "factor_raw_values": raw,
                "missing_fields": [],
                "risk_flags": [],
            })

        value_scores = self._dimension_score(raw_rows, ["pb_inverse", "pe_ttm_inverse", "ps_ttm_inverse"])
        quality_scores = self._dimension_score(raw_rows, ["roe", "operating_cash_flow_to_profit", "gross_margin", "debt_ratio_inverse"])
        momentum_scores = self._dimension_score(raw_rows, ["return_60d_exclude_5d", "return_120d_exclude_5d", "ma_trend_score"])

        for index, row in enumerate(raw_rows):
            row["value_score"] = value_scores[index]
            row["quality_score"] = quality_scores[index]
            row["momentum_score"] = momentum_scores[index]
            row["risk_penalty"] = 0.0
            row["liquidity_flag"] = "ok"
        return raw_rows

    def _dimension_score(self, rows: List[Dict[str, object]], factor_names: List[str]) -> List[float]:
        per_factor_scores = []
        for name in factor_names:
            values = [float(row["factor_raw_values"][name]) for row in rows]
            per_factor_scores.append(rank_percentile(values, higher_is_better=True))
        result = []
        for row_index in range(len(rows)):
            result.append(round(sum(scores[row_index] for scores in per_factor_scores) / len(per_factor_scores), 4))
        return result

    def _momentum_returns(self, trade_date: str, codes: List[str]) -> Dict[str, Dict[str, float]]:
        placeholders = ", ".join(["?"] * len(codes))
        rows = self.repository.fetch_dicts(
            f"""
            select trade_date, code, close
            from daily_bar
            where trade_date <= ? and code in ({placeholders})
            order by code, trade_date
            """,
            [trade_date, *codes],
        )
        by_code: Dict[str, List[Dict[str, object]]] = {code: [] for code in codes}
        for row in rows:
            by_code[str(row["code"])].append(row)
        result = {}
        for code, series in by_code.items():
            closes = [float(row["close"]) for row in series]
            latest_index = len(closes) - 6
            start_60 = max(0, latest_index - 60)
            start_120 = max(0, latest_index - 120)
            latest = closes[latest_index]
            ret_60 = latest / closes[start_60] - 1.0
            ret_120 = latest / closes[start_120] - 1.0
            ma5 = sum(closes[-5:]) / 5
            ma20 = sum(closes[-20:]) / 20
            result[code] = {
                "return_60d_exclude_5d": ret_60,
                "return_120d_exclude_5d": ret_120,
                "ma_trend_score": 1.0 if ma5 >= ma20 else 0.0,
            }
        return result
```

- [ ] **Step 4: Implement scoring service**

Create `quant-a/quant/scoring/service.py`:

```python
from typing import Dict, List


class ScoringService:
    def __init__(self, value_weight: float = 0.30, quality_weight: float = 0.35, momentum_weight: float = 0.25):
        self.value_weight = value_weight
        self.quality_weight = quality_weight
        self.momentum_weight = momentum_weight

    def score(
        self,
        trade_date: str,
        factors: List[Dict[str, object]],
        data_version: str,
        model_version: str,
    ) -> List[Dict[str, object]]:
        scored = []
        for row in factors:
            total = (
                float(row["value_score"]) * self.value_weight
                + float(row["quality_score"]) * self.quality_weight
                + float(row["momentum_score"]) * self.momentum_weight
                - float(row["risk_penalty"])
            )
            scored.append({
                "trade_date": trade_date,
                "code": row["code"],
                "name": row["name"],
                "industry": row["industry"],
                "value_score": round(float(row["value_score"]), 4),
                "quality_score": round(float(row["quality_score"]), 4),
                "momentum_score": round(float(row["momentum_score"]), 4),
                "risk_penalty": round(float(row["risk_penalty"]), 4),
                "liquidity_flag": row["liquidity_flag"],
                "total_score": round(total, 4),
                "rank": 0,
                "factor_raw_values": row["factor_raw_values"],
                "factor_scores": {
                    "value": row["value_score"],
                    "quality": row["quality_score"],
                    "momentum": row["momentum_score"],
                },
                "missing_fields": row["missing_fields"],
                "risk_flags": row["risk_flags"],
                "data_version": data_version,
                "model_version": model_version,
            })
        scored.sort(key=lambda item: item["total_score"], reverse=True)
        for index, item in enumerate(scored, start=1):
            item["rank"] = index
        return scored
```

- [ ] **Step 5: Run scoring tests**

Run:

```powershell
cd quant-a
python -m pytest tests/test_scoring.py -v
```

Expected:

```text
2 passed
```

- [ ] **Step 6: Commit factor scoring**

```powershell
git add quant-a/quant/factors/engine.py quant-a/quant/scoring/service.py quant-a/tests/test_scoring.py
git commit -m "feat: score quant-a vqm baseline"
```

---

### Task 7: Implement Portfolio, Backtest, Risk, Experiments, and Reports

**Files:**
- Create: `quant-a/quant/portfolio/service.py`
- Create: `quant-a/quant/backtest/service.py`
- Create: `quant-a/quant/risk/service.py`
- Create: `quant-a/quant/experiments/service.py`
- Create: `quant-a/quant/reports/service.py`
- Create: `quant-a/tests/test_backtest.py`

- [ ] **Step 1: Write backtest test**

Create `quant-a/tests/test_backtest.py`:

```python
from pathlib import Path

from quant.backtest.service import BacktestService
from quant.calendar.service import TradingCalendarService
from quant.factors.engine import FactorEngine
from quant.portfolio.service import PortfolioService
from quant.providers.mock_provider import MockProvider
from quant.reports.service import ReportService
from quant.risk.service import RiskService
from quant.scoring.service import ScoringService
from quant.services.pipeline import QuantPipeline
from quant.storage.repository import QuantRepository
from quant.universe.service import UniverseService


def build_scores(repository: QuantRepository, trade_date: str):
    universe = UniverseService(repository).build_universe(trade_date, ["CSI300"], 120, 50000000, False, True)
    factors = FactorEngine(repository).calculate(trade_date, universe)
    return ScoringService().score(trade_date, factors, repository.latest_data_version(), "v0.1")


def test_monthly_backtest_outputs_report(tmp_path: Path):
    repository = QuantRepository(tmp_path / "quant.duckdb")
    QuantPipeline(repository=repository, provider=MockProvider()).sync_data("2024-01-02", "2024-03-31", ["CSI300"])
    calendar = TradingCalendarService(repository)
    portfolio = PortfolioService(top_n=3, single_stock_weight_limit=0.05)
    backtest = BacktestService(repository, calendar, portfolio)
    scores_by_date = {
        "2024-01-31": build_scores(repository, "2024-01-31"),
        "2024-02-29": build_scores(repository, "2024-02-29"),
    }

    result = backtest.run("2024-01-02", "2024-03-31", scores_by_date, initial_cash=1000000.0)
    report = ReportService(RiskService()).build_report("exp-test", result)

    assert result["experiment_id"].startswith("bt-")
    assert len(result["nav"]) > 0
    assert len(result["orders"]) > 0
    assert report["experiment_id"] == "exp-test"
    assert "known_biases" in report
    assert report["metrics"]["max_drawdown"] <= 0
```

- [ ] **Step 2: Run backtest test and confirm imports fail**

Run:

```powershell
cd quant-a
python -m pytest tests/test_backtest.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'quant.backtest'
```

- [ ] **Step 3: Implement portfolio service**

Create `quant-a/quant/portfolio/service.py`:

```python
from typing import Dict, List


class PortfolioService:
    def __init__(self, top_n: int = 30, single_stock_weight_limit: float = 0.05):
        self.top_n = top_n
        self.single_stock_weight_limit = single_stock_weight_limit

    def build_targets(self, scores: List[Dict[str, object]]) -> List[Dict[str, object]]:
        selected = scores[: self.top_n]
        if not selected:
            return []
        equal_weight = min(1.0 / len(selected), self.single_stock_weight_limit)
        return [
            {
                "code": item["code"],
                "name": item["name"],
                "industry": item["industry"],
                "target_weight": equal_weight,
                "rank": item["rank"],
                "total_score": item["total_score"],
            }
            for item in selected
        ]
```

- [ ] **Step 4: Implement backtest service**

Create `quant-a/quant/backtest/service.py`:

```python
from typing import Dict, List
from uuid import uuid4

from quant.calendar.service import TradingCalendarService
from quant.portfolio.service import PortfolioService
from quant.storage.repository import QuantRepository


class BacktestService:
    def __init__(self, repository: QuantRepository, calendar: TradingCalendarService, portfolio: PortfolioService):
        self.repository = repository
        self.calendar = calendar
        self.portfolio = portfolio

    def run(
        self,
        start_date: str,
        end_date: str,
        scores_by_date: Dict[str, List[Dict[str, object]]],
        initial_cash: float,
    ) -> Dict[str, object]:
        experiment_id = f"bt-{uuid4().hex[:12]}"
        rebalance_dates = [
            day for day in self.calendar.month_end_trade_dates(start_date, end_date)
            if day in scores_by_date
        ]
        cash = initial_cash
        holdings: Dict[str, float] = {}
        orders = []
        nav = []

        for signal_date in rebalance_dates:
            trade_date = self.calendar.next_trade_date(signal_date)
            targets = self.portfolio.build_targets(scores_by_date[signal_date])
            target_codes = {target["code"] for target in targets}

            for code, quantity in list(holdings.items()):
                if code not in target_codes and quantity > 0:
                    price = self._open_price(trade_date, code)
                    cash += quantity * price * (1 - 0.00025 - 0.0005)
                    orders.append(self._order(signal_date, trade_date, code, "sell", quantity, price, "filled", ""))
                    holdings[code] = 0

            portfolio_value = cash + sum(quantity * self._close_price(signal_date, code) for code, quantity in holdings.items())
            for target in targets:
                price = self._open_price(trade_date, str(target["code"]))
                target_amount = portfolio_value * float(target["target_weight"])
                quantity = int(target_amount / price / 100) * 100
                if quantity <= 0:
                    orders.append(self._order(signal_date, trade_date, str(target["code"]), "buy", 0, price, "rejected", "lot_size_reject"))
                    continue
                cost = quantity * price * (1 + 0.00025)
                if cost > cash:
                    orders.append(self._order(signal_date, trade_date, str(target["code"]), "buy", quantity, price, "rejected", "cash_not_enough"))
                    continue
                cash -= cost
                holdings[str(target["code"])] = holdings.get(str(target["code"]), 0) + quantity
                orders.append(self._order(signal_date, trade_date, str(target["code"]), "buy", quantity, price, "filled", ""))

        for day in self.repository.fetch_dicts("select trade_date from trade_calendar where trade_date between ? and ? order by trade_date", [start_date, end_date]):
            trade_date = str(day["trade_date"])
            market_value = sum(quantity * self._close_price(trade_date, code) for code, quantity in holdings.items())
            nav.append({
                "trade_date": trade_date,
                "cash": round(cash, 4),
                "market_value": round(market_value, 4),
                "total_asset": round(cash + market_value, 4),
                "nav": round((cash + market_value) / initial_cash, 6),
            })

        return {
            "experiment_id": experiment_id,
            "initial_cash": initial_cash,
            "nav": nav,
            "orders": orders,
            "holdings": holdings,
        }

    def _open_price(self, trade_date: str, code: str) -> float:
        rows = self.repository.fetch_dicts("select open from daily_bar where trade_date = ? and code = ?", [trade_date, code])
        if not rows:
            raise ValueError(f"Missing open price for {code} on {trade_date}")
        return float(rows[0]["open"]) * 1.001

    def _close_price(self, trade_date: str, code: str) -> float:
        rows = self.repository.fetch_dicts("select close from daily_bar where trade_date = ? and code = ?", [trade_date, code])
        if not rows:
            return 0.0
        return float(rows[0]["close"])

    def _order(self, signal_date: str, trade_date: str, code: str, side: str, quantity: float, price: float, status: str, reject_reason: str) -> Dict[str, object]:
        return {
            "order_id": f"{signal_date}-{trade_date}-{code}-{side}",
            "signal_date": signal_date,
            "trade_date": trade_date,
            "code": code,
            "side": side,
            "filled_quantity": quantity if status == "filled" else 0,
            "filled_price": round(price, 4),
            "order_status": status,
            "reject_reason": reject_reason,
        }
```

- [ ] **Step 5: Implement risk service**

Create `quant-a/quant/risk/service.py`:

```python
from typing import Dict, List


class RiskService:
    def known_biases(self) -> List[Dict[str, str]]:
        return [
            {
                "bias_type": "data_source",
                "severity": "medium",
                "affected_period": "2024-01-02 to 2024-03-31",
                "affected_fields": "mock market, valuation, financial",
                "impact_description": "Mock data validates the pipeline but does not represent real market behavior.",
                "mitigation": "Use production Provider and data quality checks before interpreting performance.",
            },
            {
                "bias_type": "execution_price",
                "severity": "medium",
                "affected_period": "all backtest dates",
                "affected_fields": "open price, slippage",
                "impact_description": "The first backtest uses open price plus fixed slippage rather than minute VWAP.",
                "mitigation": "Disclose the assumption and add VWAP data in a later execution model.",
            },
        ]
```

- [ ] **Step 6: Implement experiment service**

Create `quant-a/quant/experiments/service.py`:

```python
from datetime import datetime
from typing import Dict
from uuid import uuid4


class ExperimentService:
    def create_experiment(self, model_version: str, data_version: str, config_version: str) -> Dict[str, str]:
        return {
            "experiment_id": f"exp-{uuid4().hex[:12]}",
            "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "model_version": model_version,
            "data_version": data_version,
            "config_version": config_version,
            "decision": "watch_only",
        }
```

- [ ] **Step 7: Implement report service**

Create `quant-a/quant/reports/service.py`:

```python
from typing import Dict

from quant.risk.service import RiskService


class ReportService:
    def __init__(self, risk_service: RiskService):
        self.risk_service = risk_service

    def build_report(self, experiment_id: str, backtest_result: Dict[str, object]) -> Dict[str, object]:
        nav = backtest_result["nav"]
        nav_values = [float(item["nav"]) for item in nav]
        peak = nav_values[0] if nav_values else 1.0
        max_drawdown = 0.0
        for value in nav_values:
            peak = max(peak, value)
            max_drawdown = min(max_drawdown, value / peak - 1.0)
        return {
            "experiment_id": experiment_id,
            "metrics": {
                "start_nav": nav_values[0] if nav_values else 1.0,
                "end_nav": nav_values[-1] if nav_values else 1.0,
                "total_return": round((nav_values[-1] - 1.0) if nav_values else 0.0, 6),
                "max_drawdown": round(max_drawdown, 6),
                "order_count": len(backtest_result["orders"]),
            },
            "nav": nav,
            "orders": backtest_result["orders"],
            "known_biases": self.risk_service.known_biases(),
        }
```

- [ ] **Step 8: Run backtest tests**

Run:

```powershell
cd quant-a
python -m pytest tests/test_backtest.py -v
```

Expected:

```text
1 passed
```

- [ ] **Step 9: Commit backtest and reporting**

```powershell
git add quant-a/quant/portfolio/service.py quant-a/quant/backtest/service.py quant-a/quant/risk/service.py quant-a/quant/experiments/service.py quant-a/quant/reports/service.py quant-a/tests/test_backtest.py
git commit -m "feat: add quant-a backtest report"
```

---

### Task 8: Wire Pipeline to FastAPI Endpoints

**Files:**
- Modify: `quant-a/quant/services/pipeline.py`
- Modify: `quant-a/quant/api/routes.py`
- Create: `quant-a/tests/test_api_pipeline.py`

- [ ] **Step 1: Write API pipeline tests**

Create `quant-a/tests/test_api_pipeline.py`:

```python
from fastapi.testclient import TestClient

from main import app


def test_data_sync_and_scoring_pipeline():
    client = TestClient(app)

    sync_response = client.post("/api/data/sync", json={
        "start_date": "2024-01-02",
        "end_date": "2024-03-31",
        "index_codes": ["CSI300"],
    })
    assert sync_response.status_code == 200
    assert sync_response.json()["success"] is True

    score_response = client.post("/api/scores/run", json={
        "trade_date": "2024-03-29",
        "index_codes": ["CSI300"],
    })
    assert score_response.status_code == 200
    payload = score_response.json()
    assert payload["success"] is True
    assert len(payload["data"]["scores"]) == 6


def test_backtest_report_pipeline():
    client = TestClient(app)
    client.post("/api/data/sync", json={
        "start_date": "2024-01-02",
        "end_date": "2024-03-31",
        "index_codes": ["CSI300"],
    })

    response = client.post("/api/backtests/run", json={
        "start_date": "2024-01-02",
        "end_date": "2024-03-31",
        "index_codes": ["CSI300"],
        "initial_cash": 1000000,
    })

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["report"]["metrics"]["order_count"] > 0
    assert payload["data"]["report"]["known_biases"]
```

- [ ] **Step 2: Run API tests and confirm route failures**

Run:

```powershell
cd quant-a
python -m pytest tests/test_api_pipeline.py -v
```

Expected:

```text
404 Not Found
```

- [ ] **Step 3: Extend pipeline orchestration**

Modify `quant-a/quant/services/pipeline.py` to include:

```python
from pathlib import Path
from typing import Dict, List, Optional

from quant.backtest.service import BacktestService
from quant.calendar.service import TradingCalendarService
from quant.factors.engine import FactorEngine
from quant.portfolio.service import PortfolioService
from quant.providers.mock_provider import MockProvider
from quant.reports.service import ReportService
from quant.risk.service import RiskService
from quant.scoring.service import ScoringService
from quant.storage.repository import QuantRepository
from quant.universe.service import UniverseService


class QuantPipeline:
    def __init__(self, repository: Optional[QuantRepository] = None, provider: Optional[MockProvider] = None):
        self.repository = repository or QuantRepository(Path("data/quant.duckdb"))
        self.provider = provider or MockProvider()

    def sync_data(self, start_date: str, end_date: str, index_codes: List[str]) -> Dict[str, object]:
        calendar = self.provider.get_trade_calendar(start_date, end_date)
        stocks = self.provider.get_stock_basic()
        daily_bars = self.provider.get_daily_bars(start_date, end_date)
        valuations = self.provider.get_valuation(start_date, end_date)
        financials = self.provider.get_financials()
        members = self.provider.get_index_members(index_codes, end_date)
        data_version = self.provider.data_version
        counts = {
            "calendar_count": self.repository.replace_table("trade_calendar", calendar),
            "stock_count": self.repository.replace_table("stock_basic", stocks),
            "daily_bar_count": self.repository.replace_table("daily_bar", daily_bars),
            "valuation_count": self.repository.replace_table("valuation", valuations),
            "financial_count": self.repository.replace_table("financial", financials),
            "index_member_count": self.repository.replace_table("index_member", members),
        }
        self.repository.record_data_version(data_version, "mock", start_date, end_date)
        return {"data_version": data_version, **counts}

    def run_scores(self, trade_date: str, index_codes: List[str]) -> Dict[str, object]:
        universe = UniverseService(self.repository).build_universe(trade_date, index_codes, 120, 50000000, False, True)
        factors = FactorEngine(self.repository).calculate(trade_date, universe)
        scores = ScoringService().score(trade_date, factors, self.repository.latest_data_version(), "v0.1")
        return {
            "trade_date": trade_date,
            "scores": scores,
        }

    def run_backtest(self, start_date: str, end_date: str, index_codes: List[str], initial_cash: float) -> Dict[str, object]:
        calendar = TradingCalendarService(self.repository)
        score_dates = calendar.month_end_trade_dates(start_date, end_date)
        scores_by_date = {}
        for trade_date in score_dates:
            try:
                scores_by_date[trade_date] = self.run_scores(trade_date, index_codes)["scores"]
            except ValueError:
                continue
        backtest = BacktestService(self.repository, calendar, PortfolioService(top_n=3, single_stock_weight_limit=0.05))
        result = backtest.run(start_date, end_date, scores_by_date, initial_cash)
        report = ReportService(RiskService()).build_report(result["experiment_id"], result)
        return {
            "backtest": result,
            "report": report,
        }
```

- [ ] **Step 4: Add request models and endpoints**

Modify `quant-a/quant/api/routes.py` to:

```python
from typing import List

from fastapi import APIRouter
from pydantic import BaseModel

from quant.common.config import load_app_config
from quant.common.response import success
from quant.services.pipeline import QuantPipeline

router = APIRouter(prefix="/api")
pipeline = QuantPipeline()


class SyncRequest(BaseModel):
    start_date: str
    end_date: str
    index_codes: List[str]


class ScoreRequest(BaseModel):
    trade_date: str
    index_codes: List[str]


class BacktestRequest(BaseModel):
    start_date: str
    end_date: str
    index_codes: List[str]
    initial_cash: float


@router.get("/health")
def health():
    return success({"service": "quant-a", "status": "ok", "port": 5175})


@router.get("/status")
def status():
    config = load_app_config()
    return success({
        "service": config["app"]["name"],
        "provider": config["provider"]["active"],
        "model_version": config["versions"]["model_version"],
        "config_version": config["versions"]["config_version"],
        "storage": config["storage"],
    })


@router.post("/data/sync")
def sync_data(request: SyncRequest):
    return success(pipeline.sync_data(request.start_date, request.end_date, request.index_codes))


@router.post("/scores/run")
def run_scores(request: ScoreRequest):
    return success(pipeline.run_scores(request.trade_date, request.index_codes))


@router.post("/backtests/run")
def run_backtest(request: BacktestRequest):
    return success(pipeline.run_backtest(request.start_date, request.end_date, request.index_codes, request.initial_cash))
```

- [ ] **Step 5: Run API pipeline tests**

Run:

```powershell
cd quant-a
python -m pytest tests/test_api_pipeline.py -v
```

Expected:

```text
2 passed
```

- [ ] **Step 6: Run full `quant-a` test suite**

Run:

```powershell
cd quant-a
python -m pytest -v
```

Expected:

```text
all tests passed
```

- [ ] **Step 7: Commit API pipeline**

```powershell
git add quant-a/quant/services/pipeline.py quant-a/quant/api/routes.py quant-a/tests/test_api_pipeline.py
git commit -m "feat: expose quant-a pipeline api"
```

---

### Task 9: Build Workbench UI

**Files:**
- Modify: `quant-a/web/index.html`
- Create: `quant-a/web/app.js`
- Create: `quant-a/web/styles.css`
- Modify: `quant-a/main.py`
- Modify: `quant-a/tests/test_health.py`

- [ ] **Step 1: Extend workbench test**

Modify `test_workbench_page_is_served` in `quant-a/tests/test_health.py`:

```python
def test_workbench_page_is_served():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "quant-a" in response.text
    assert "多因子量化研究工作台" in response.text
    assert "运行回测" in response.text
```

- [ ] **Step 2: Run workbench test and confirm it fails on missing text**

Run:

```powershell
cd quant-a
python -m pytest tests/test_health.py::test_workbench_page_is_served -v
```

Expected:

```text
AssertionError: assert '运行回测' in response.text
```

- [ ] **Step 3: Implement workbench HTML**

Replace `quant-a/web/index.html` with:

```html
<!doctype html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>quant-a 多因子量化研究工作台</title>
    <link rel="stylesheet" href="/static/styles.css">
</head>
<body>
<main class="app-shell">
    <section class="header-band">
        <div>
            <p class="eyebrow">quant-a</p>
            <h1>多因子量化研究工作台</h1>
            <p>数据版本、因子评分、月度回测和风险披露集中在一个可复现工作流中。</p>
        </div>
        <div class="status-panel">
            <span id="service-status">检测中</span>
            <strong id="model-version">v0.1</strong>
        </div>
    </section>

    <section class="action-bar">
        <button id="sync-button" type="button">同步数据</button>
        <button id="score-button" type="button">运行评分</button>
        <button id="backtest-button" type="button">运行回测</button>
    </section>

    <section class="grid">
        <article>
            <h2>Top N 榜单</h2>
            <table>
                <thead>
                <tr><th>排名</th><th>代码</th><th>名称</th><th>行业</th><th>总分</th></tr>
                </thead>
                <tbody id="score-table"></tbody>
            </table>
        </article>
        <article>
            <h2>回测报告</h2>
            <dl id="report-metrics"></dl>
            <h3>已知偏差</h3>
            <ul id="bias-list"></ul>
        </article>
    </section>
</main>
<script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 4: Implement workbench JavaScript**

Create `quant-a/web/app.js`:

```javascript
const state = {
    startDate: "2024-01-02",
    endDate: "2024-03-31",
    tradeDate: "2024-03-29",
    indexCodes: ["CSI300"]
};

async function api(path, options = {}) {
    const response = await fetch(path, {
        headers: { "Content-Type": "application/json" },
        ...options
    });
    const payload = await response.json();
    if (!payload.success) {
        throw new Error(payload.message || "请求失败");
    }
    return payload.data;
}

function renderScores(scores) {
    const table = document.querySelector("#score-table");
    table.innerHTML = scores.map((item) => `
        <tr>
            <td>${item.rank}</td>
            <td>${item.code}</td>
            <td>${item.name}</td>
            <td>${item.industry}</td>
            <td>${item.total_score.toFixed(2)}</td>
        </tr>
    `).join("");
}

function renderReport(report) {
    const metrics = document.querySelector("#report-metrics");
    metrics.innerHTML = Object.entries(report.metrics).map(([key, value]) => `
        <dt>${key}</dt><dd>${value}</dd>
    `).join("");
    const biasList = document.querySelector("#bias-list");
    biasList.innerHTML = report.known_biases.map((bias) => `
        <li><strong>${bias.bias_type}</strong>：${bias.impact_description}</li>
    `).join("");
}

async function loadStatus() {
    const status = await api("/api/status");
    document.querySelector("#service-status").textContent = "可用";
    document.querySelector("#model-version").textContent = status.model_version;
}

document.querySelector("#sync-button").addEventListener("click", async () => {
    await api("/api/data/sync", {
        method: "POST",
        body: JSON.stringify({
            start_date: state.startDate,
            end_date: state.endDate,
            index_codes: state.indexCodes
        })
    });
});

document.querySelector("#score-button").addEventListener("click", async () => {
    const data = await api("/api/scores/run", {
        method: "POST",
        body: JSON.stringify({
            trade_date: state.tradeDate,
            index_codes: state.indexCodes
        })
    });
    renderScores(data.scores);
});

document.querySelector("#backtest-button").addEventListener("click", async () => {
    const data = await api("/api/backtests/run", {
        method: "POST",
        body: JSON.stringify({
            start_date: state.startDate,
            end_date: state.endDate,
            index_codes: state.indexCodes,
            initial_cash: 1000000
        })
    });
    renderReport(data.report);
});

loadStatus().catch(() => {
    document.querySelector("#service-status").textContent = "不可用";
});
```

- [ ] **Step 5: Implement workbench CSS**

Create `quant-a/web/styles.css`:

```css
* {
    box-sizing: border-box;
}

body {
    margin: 0;
    color: #172026;
    background: #f5f7fb;
    font-family: "Microsoft YaHei", "Segoe UI", system-ui, sans-serif;
}

.app-shell {
    width: min(1180px, calc(100vw - 32px));
    margin: 0 auto;
    padding: 32px 0;
}

.header-band {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 24px;
    padding: 28px 0;
    border-bottom: 1px solid #d8e1ea;
}

.eyebrow {
    margin: 0 0 8px;
    color: #3e6b89;
    font-weight: 800;
}

h1, h2, h3, p {
    margin-top: 0;
}

h1 {
    margin-bottom: 12px;
    font-size: 34px;
}

.status-panel {
    min-width: 180px;
    display: grid;
    gap: 8px;
    padding: 16px;
    border: 1px solid #d8e1ea;
    border-radius: 8px;
    background: #ffffff;
}

.action-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin: 22px 0;
}

button {
    min-height: 40px;
    border: 0;
    border-radius: 6px;
    padding: 0 16px;
    color: #ffffff;
    background: #1f6feb;
    cursor: pointer;
    font-weight: 700;
}

.grid {
    display: grid;
    grid-template-columns: minmax(0, 1.4fr) minmax(320px, 0.8fr);
    gap: 18px;
}

article {
    padding: 18px;
    border: 1px solid #d8e1ea;
    border-radius: 8px;
    background: #ffffff;
}

table {
    width: 100%;
    border-collapse: collapse;
}

th, td {
    padding: 10px 8px;
    border-bottom: 1px solid #edf1f5;
    text-align: left;
}

dl {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px 12px;
}

dt {
    color: #5f6f7a;
}

dd {
    margin: 0;
    font-weight: 800;
}

@media (max-width: 780px) {
    .header-band,
    .grid {
        grid-template-columns: 1fr;
        display: grid;
    }
}
```

- [ ] **Step 6: Mount static assets**

Modify `quant-a/main.py`:

```python
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from quant.api.routes import router

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"

app = FastAPI(title="quant-a", version="0.1.0")
app.include_router(router)
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
def workbench():
    return (WEB_DIR / "index.html").read_text(encoding="utf-8")
```

- [ ] **Step 7: Run tests**

Run:

```powershell
cd quant-a
python -m pytest tests/test_health.py -v
```

Expected:

```text
3 passed
```

- [ ] **Step 8: Commit workbench UI**

```powershell
git add quant-a/web quant-a/main.py quant-a/tests/test_health.py
git commit -m "feat: add quant-a workbench"
```

---

### Task 10: Integrate `quant-a` into `website` and Startup Script

**Files:**
- Modify: `website/src/main/resources/static/index.html`
- Modify: `website/src/main/resources/static/css/style.css`
- Modify: `scripts/start-love5000.ps1`
- Modify: `AGENTS.md`

- [ ] **Step 1: Inspect existing homepage service card structure**

Run:

```powershell
Select-String -LiteralPath website/src/main/resources/static/index.html -Pattern "service-card" -Context 1,2
```

Expected:

```text
Existing service-card entries for lovestory, imagetemplate, blog, and python-a are visible.
```

- [ ] **Step 2: Add Quant nav link**

In `website/src/main/resources/static/index.html`, add this link near the existing stock analysis link:

```html
<a href="http://127.0.0.1:5175/" target="_blank" rel="noopener">Quant</a>
```

- [ ] **Step 3: Add Quant service card**

In the `service-grid` of `website/src/main/resources/static/index.html`, add:

```html
<a class="service-card service-card-quant" href="http://127.0.0.1:5175/" target="_blank" rel="noopener" data-health-url="http://127.0.0.1:5175/api/health" data-health-mode="no-cors">
    <strong>Quant · 5175</strong>
    <span class="service-status" aria-label="检测中" title="检测中"></span>
</a>
```

- [ ] **Step 4: Add Quant service color**

In `website/src/main/resources/static/css/style.css`, add near the existing service card color hooks:

```css
.service-card-quant {
    --accent-rgb: 246, 196, 83;
}
```

- [ ] **Step 5: Extend startup script parameters**

Modify the `param` block in `scripts/start-love5000.ps1`:

```powershell
param(
    [string]$JavaModule = "website",
    [int]$PythonPort = 5174,
    [int]$QuantPort = 5175,
    [string]$PythonCommand = "python",
    [string]$MavenCommand = "mvn",
    [switch]$SkipPython,
    [switch]$StartQuant,
    [switch]$SkipJava
)
```

- [ ] **Step 6: Add Quant startup block**

After the existing `python-a` startup block in `scripts/start-love5000.ps1`, add:

```powershell
if ($StartQuant) {
    $QuantDir = Join-Path $RootDir "quant-a"
    $QuantHealthUrl = "http://127.0.0.1:$QuantPort/api/health"

    if (-not (Test-Path -LiteralPath $QuantDir)) {
        throw "quant-a directory does not exist: $QuantDir"
    }

    try {
        $response = Invoke-RestMethod -Uri $QuantHealthUrl -Method Get -TimeoutSec 5
        if ($null -ne $response -and $response.success -eq $true) {
            Write-Host "quant-a is already running: $QuantHealthUrl"
        }
    } catch {
        Write-Host "Starting quant-a on port $QuantPort"
        $quantProcess = Start-Process `
            -FilePath $PythonCommand `
            -ArgumentList @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", [string]$QuantPort) `
            -WorkingDirectory $QuantDir `
            -WindowStyle Hidden `
            -PassThru
        Write-Host "quant-a PID: $($quantProcess.Id)"
    }
}
```

- [ ] **Step 7: Update root project docs**

In `AGENTS.md`, add `quant-a` to project overview, structure, ports, commands, and Python microservice boundary:

```markdown
- `quant-a`：专业 A 股多因子量化研究微服务，作为独立 FastAPI 服务接入，不加入 Maven 聚合模块。
```

Add command:

```bash
cd quant-a
python -m uvicorn main:app --host 127.0.0.1 --port 5175 --reload
```

Add port:

```text
quant-a：5175
```

- [ ] **Step 8: Run focused text checks**

Run:

```powershell
Select-String -LiteralPath website/src/main/resources/static/index.html -Pattern "Quant · 5175"
Select-String -LiteralPath scripts/start-love5000.ps1 -Pattern "StartQuant"
Select-String -LiteralPath AGENTS.md -Pattern "quant-a"
```

Expected:

```text
Each command prints at least one matching line.
```

- [ ] **Step 9: Commit project integration**

```powershell
git add website/src/main/resources/static/index.html website/src/main/resources/static/css/style.css scripts/start-love5000.ps1 AGENTS.md
git commit -m "feat: integrate quant-a entry"
```

---

### Task 11: Add README and Verification Pass

**Files:**
- Create: `quant-a/README.md`
- Run: full focused tests and service smoke checks

- [ ] **Step 1: Write service README**

Create `quant-a/README.md`:

```markdown
# quant-a 专业多因子量化研究系统

`quant-a` 是 `love5000` 的独立 FastAPI 微服务，用于 A 股多因子研究、股票池构建、因子评分、月度回测、实验记录和风险披露。

## 边界

- 只做量化研究、风险识别、组合候选排序和复盘辅助。
- 不构成投资建议，不承诺收益，不输出确定性买卖结论。
- 不加入 Maven 聚合模块。
- 不调用 `python-a` 内部模块，也不写入 `python-a` 的 Obsidian 目录。

## 运行

```bash
cd quant-a
python -m uvicorn main:app --host 127.0.0.1 --port 5175 --reload
```

访问：

```text
http://127.0.0.1:5175/
http://127.0.0.1:5175/api/health
http://127.0.0.1:5175/docs
```

## 测试

```bash
cd quant-a
python -m pytest -v
```

## 第一版 baseline

Value-Quality-Momentum v0.1：

- 价值：PB、PE、PS 倒数和行业内估值排序。
- 质量：ROE、经营现金流质量、毛利率、资产负债率反向。
- 动量：剔除最近 5 日后的 60 日与 120 日收益、均线趋势。

第一版使用 `mock_provider` 作为确定性演示和测试数据源。真实市场数据 Provider 扩展时必须保留数据版本、可用日和风险披露。
```

- [ ] **Step 2: Run full quant-a tests**

Run:

```powershell
cd quant-a
python -m pytest -v
```

Expected:

```text
all tests passed
```

- [ ] **Step 3: Start quant-a smoke server**

Run:

```powershell
cd quant-a
python -m uvicorn main:app --host 127.0.0.1 --port 5175
```

Expected:

```text
Uvicorn running on http://127.0.0.1:5175
```

- [ ] **Step 4: Verify health endpoint in another shell**

Run:

```powershell
curl.exe -s http://127.0.0.1:5175/api/health
```

Expected:

```json
{"success":true,"data":{"service":"quant-a","status":"ok","port":5175},"message":""}
```

- [ ] **Step 5: Verify backtest endpoint**

Run:

```powershell
curl.exe -s -H "Content-Type: application/json" -d "{\"start_date\":\"2024-01-02\",\"end_date\":\"2024-03-31\",\"index_codes\":[\"CSI300\"],\"initial_cash\":1000000}" http://127.0.0.1:5175/api/backtests/run
```

Expected:

```text
Response JSON has "success": true and data.report.metrics.order_count greater than 0.
```

- [ ] **Step 6: Stop the smoke server**

Press:

```text
Ctrl+C
```

Expected:

```text
Application shutdown complete
```

- [ ] **Step 7: Commit README and verification support**

```powershell
git add quant-a/README.md
git commit -m "docs: document quant-a service"
```

---

## Self-Review Checklist

- Spec coverage:
  - Independent `quant-a` service: Tasks 1, 9, 10, 11.
  - FastAPI + Uvicorn: Tasks 1, 11.
  - Config files: Task 2.
  - Provider interface and mock/eastmoney boundary: Task 3.
  - DuckDB storage and data versions: Task 4.
  - Index universe: Task 5.
  - Value-Quality-Momentum scoring: Task 6.
  - Monthly backtest and reports: Task 7.
  - API endpoints: Task 8.
  - Workbench page: Task 9.
  - `website` and startup integration: Task 10.
  - README and smoke verification: Task 11.

- Type consistency:
  - Provider rows use dataclasses and repository writes via `asdict`.
  - `QuantRepository.fetch_dicts` returns mappings consumed by services.
  - Scores consistently use `trade_date`, `code`, `name`, `industry`, `total_score`, `rank`, `data_version`, and `model_version`.
  - API response shape is always `{success, data, message}` for successful endpoints.

- Known implementation caution:
  - If the active Python environment does not have dependencies installed, install from `quant-a/requirements.txt` before running tests.
  - If port `5175` is already occupied during smoke testing, stop the existing process or run Uvicorn with another port and update the curl URL for that smoke test.
