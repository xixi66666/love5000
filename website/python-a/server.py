from __future__ import annotations

import json
import math
import os
import re
import statistics
import time
import http.client
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Iterable, List, Optional

from services.account_service import AccountService
from services.knowledge_graph_service import ObsidianKnowledgeGraphService
from services.obsidian_service import ObsidianTradingService
from services.stock_match_service import StockMatchService
from services.stock_metadata_service import StockMetadataService
from services.storage_service import JsonStore
from services.trade_service import TradeService
from services.vision_parse_service import VisionParseService


ROOT = Path(__file__).resolve().parent
OBSIDIAN_ROOT = Path(os.environ.get("ASHARE_OBSIDIAN_ROOT", ROOT / "obsidian-vault" / "A股AI")).resolve()
DATA_ROOT = OBSIDIAN_ROOT / "data"
PORT = int(os.environ.get("PORT", "5174"))
CACHE_TTL_SECONDS = 180
FETCH_WORKERS = 6

WATCHLIST = [
]

DEEPSEEK_API_BASE = os.environ.get("DEEPSEEK_API_BASE", "https://api.deepseek.com").rstrip("/")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro")
VISION_API_BASE = os.environ.get("VISION_API_BASE", DEEPSEEK_API_BASE).rstrip("/")
VISION_MODEL = os.environ.get("VISION_MODEL", os.environ.get("DEEPSEEK_VISION_MODEL", "gpt-4o-mini"))

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/",
}

STOCK_CACHE: Dict[str, Dict[str, Any]] = {}
WATCHLIST_CACHE: Dict[str, Any] = {"time": 0.0, "payload": None}
CACHE_LOCK = Lock()


class DataSourceError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def read_local_secret(name: str) -> str:
    value = os.environ.get(name)
    if value:
        return value.strip()
    config_path = ROOT / "deepseek.local.json"
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8-sig"))
            return str(data.get(name) or data.get(name.lower()) or "").strip()
        except Exception:
            return ""
    return ""


def trading_services() -> Dict[str, Any]:
    store = JsonStore(DATA_ROOT)
    return {
        "account": AccountService(store),
        "trade": TradeService(store),
        "stock_match": StockMatchService(store, seed_rows=read_watchlist()),
        "obsidian": ObsidianTradingService(OBSIDIAN_ROOT),
        "metadata": StockMetadataService(DATA_ROOT),
        "knowledge_graph": ObsidianKnowledgeGraphService(OBSIDIAN_ROOT),
        "vision": VisionParseService(
            api_key=read_local_secret("VISION_API_KEY"),
            api_base=VISION_API_BASE,
            model=VISION_MODEL,
        ),
    }


def secid_for_code(code: str) -> str:
    code = code.strip()
    if not re.fullmatch(r"\d{6}", code):
        raise ValueError(f"Invalid A-share code: {code}")
    market = "1" if code.startswith(("6", "9")) else "0"
    return f"{market}.{code}"


def eastmoney_json(url: str) -> Dict[str, Any]:
    try:
        completed = subprocess.run(
            [
                "curl.exe",
                "-L",
                "--silent",
                "--show-error",
                "--max-time",
                "15",
                "--retry",
                "2",
                "--retry-delay",
                "1",
                "--retry-all-errors",
                "-H",
                "Referer: https://quote.eastmoney.com/",
                "-H",
                f"User-Agent: {HTTP_HEADERS['User-Agent']}",
                url,
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        payload = completed.stdout
        data = json.loads(payload)
        if data.get("rc") not in (0, None):
            raise DataSourceError(f"Eastmoney returned rc={data.get('rc')}")
        if data.get("data") is None:
            raise DataSourceError("Eastmoney returned empty data")
        return data
    except Exception:
        pass

    request = urllib.request.Request(url, headers=HTTP_HEADERS)
    last_error: Optional[BaseException] = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=12) as response:
                payload = response.read().decode("utf-8")
            break
        except (urllib.error.URLError, TimeoutError, http.client.RemoteDisconnected, ConnectionError) as exc:
            last_error = exc
            time.sleep(0.3 + attempt * 0.5)
    else:
        raise DataSourceError(f"Eastmoney request failed: {last_error}") from last_error
    data = json.loads(payload)
    if data.get("rc") not in (0, None):
        raise DataSourceError(f"Eastmoney returned rc={data.get('rc')}")
    if data.get("data") is None:
        raise DataSourceError("Eastmoney returned empty data")
    return data


def scaled_price(value: Any) -> Optional[float]:
    if value in (None, "-", ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= -100000:
        return None
    return round(number / 100, 2)


def scaled_percent(value: Any) -> Optional[float]:
    if value in (None, "-", ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if abs(number) > 100000:
        return None
    return round(number / 100, 2)


def as_float(value: Any, digits: Optional[int] = None) -> Optional[float]:
    if value in (None, "-", ""):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return round(result, digits) if digits is not None else result


def mean(values: Iterable[float]) -> Optional[float]:
    values = list(values)
    return sum(values) / len(values) if values else None


def moving_average(values: List[float], window: int) -> List[Optional[float]]:
    result: List[Optional[float]] = []
    for index in range(len(values)):
        if index + 1 < window:
            result.append(None)
            continue
        result.append(round(sum(values[index - window + 1 : index + 1]) / window, 4))
    return result


def percentile_rank(values: List[float], current: float) -> float:
    if not values:
        return 0.0
    less_or_equal = sum(1 for value in values if value <= current)
    return round(less_or_equal / len(values) * 100, 1)


def parse_kline(raw: str) -> Dict[str, Any]:
    fields = raw.split(",")
    return {
        "date": fields[0],
        "open": as_float(fields[1], 2),
        "close": as_float(fields[2], 2),
        "high": as_float(fields[3], 2),
        "low": as_float(fields[4], 2),
        "volume": as_float(fields[5], 0),
        "amount": as_float(fields[6], 2),
        "amplitude": as_float(fields[7], 2),
        "pct_change": as_float(fields[8], 2),
        "change": as_float(fields[9], 2),
        "turnover_rate": as_float(fields[10], 2),
    }


def classify_risk(distribution_score: int, risk_text: str) -> str:
    if distribution_score >= 72 or "跌破30日" in risk_text:
        return "高"
    if distribution_score >= 45 or "跌破10日" in risk_text:
        return "中"
    return "低"


def trend_status(latest: Dict[str, Any], ma5: Optional[float], ma10: Optional[float], ma30: Optional[float]) -> str:
    close = latest["close"]
    if ma5 and ma10 and ma30:
        if close >= ma5 > ma10 > ma30:
            return "多头排列"
        if close < ma30:
            return "跌破30日"
        if close < ma10:
            return "跌破10日"
        if close >= ma30 and ma5 >= ma30:
            return "震荡修复"
    return "等待确认"


def trend_score(latest: Dict[str, Any], ma5: Optional[float], ma10: Optional[float], ma30: Optional[float]) -> int:
    close = latest["close"]
    score = 50
    if ma5 and close >= ma5:
        score += 12
    if ma10 and close >= ma10:
        score += 10
    if ma30 and close >= ma30:
        score += 10
    if ma5 and ma10 and ma5 > ma10:
        score += 8
    if ma10 and ma30 and ma10 > ma30:
        score += 8
    if latest.get("pct_change", 0) and latest["pct_change"] > 0:
        score += min(8, int(latest["pct_change"] * 1.5))
    return max(0, min(100, score))


def distribution_score(kline: List[Dict[str, Any]], turnover_percentile: float) -> int:
    latest = kline[-1]
    close = latest["close"]
    open_price = latest["open"]
    high = latest["high"]
    low = latest["low"]
    recent = kline[-60:] if len(kline) >= 60 else kline
    high_60 = max(item["high"] for item in recent if item["high"] is not None)
    upper_shadow = 0.0
    if high and low and high > low:
        upper_shadow = (high - max(close, open_price)) / (high - low) * 100
    high_position = close / high_60 * 100 if high_60 else 0
    score = 0
    if high_position >= 92:
        score += 25
    elif high_position >= 84:
        score += 15
    if turnover_percentile >= 85:
        score += 25
    elif turnover_percentile >= 70:
        score += 15
    if upper_shadow >= 45:
        score += 20
    elif upper_shadow >= 25:
        score += 10
    if abs(latest.get("pct_change") or 0) <= 1 and turnover_percentile >= 70:
        score += 15
    if close < open_price and turnover_percentile >= 65:
        score += 15
    return max(0, min(100, score))


def status_from_scores(trend: int, turnover_percentile: float, distribution: int, ma_state: str) -> str:
    if distribution >= 72:
        return "疑似派发"
    if distribution >= 58 and turnover_percentile >= 80:
        return "疑似诱多"
    if "跌破" in ma_state:
        return "风险回避"
    if trend >= 78 and turnover_percentile < 85:
        return "低吸候选"
    if trend >= 70 and turnover_percentile >= 70:
        return "高换手接力"
    if trend >= 62:
        return "等待确认"
    return "观察"


def quote_url(code: str) -> str:
    fields = ",".join(
        [
            "f43",
            "f44",
            "f45",
            "f46",
            "f47",
            "f48",
            "f57",
            "f58",
            "f60",
            "f85",
            "f116",
            "f168",
            "f170",
            "f292",
        ]
    )
    return f"https://push2.eastmoney.com/api/qt/stock/get?secid={secid_for_code(code)}&fields={fields}"


def kline_url(code: str) -> str:
    fields1 = "f1,f2,f3,f4,f5,f6"
    fields2 = "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
    return (
        "https://push2his.eastmoney.com/api/qt/stock/kline/get?"
        f"secid={secid_for_code(code)}&fields1={fields1}&fields2={fields2}"
        "&klt=101&fqt=1&beg=20240101&end=20500101"
    )


def fetch_stock(code: str, meta: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    meta = meta or {}
    metadata = StockMetadataService(DATA_ROOT).get_stock_metadata(code, fallback=meta)
    quote_data = eastmoney_json(quote_url(code))["data"]
    kline_data = eastmoney_json(kline_url(code))["data"]
    klines = [parse_kline(raw) for raw in kline_data.get("klines", [])]
    if len(klines) < 35:
        raise DataSourceError(f"Not enough kline data for {code}")

    closes = [item["close"] for item in klines if item["close"] is not None]
    ma5 = moving_average(closes, 5)
    ma10 = moving_average(closes, 10)
    ma30 = moving_average(closes, 30)
    latest = klines[-1]
    ma5_latest = ma5[-1]
    ma10_latest = ma10[-1]
    ma30_latest = ma30[-1]
    turnover_values = [item["turnover_rate"] for item in klines[-250:] if item["turnover_rate"] is not None]
    latest_turnover = latest["turnover_rate"] or scaled_percent(quote_data.get("f168")) or 0.0
    turnover_percentile = percentile_rank(turnover_values, latest_turnover)
    avg20_turnover = mean(turnover_values[-20:]) or 0.0
    turnover_ratio = latest_turnover / avg20_turnover if avg20_turnover else 0
    ma_state = trend_status(latest, ma5_latest, ma10_latest, ma30_latest)
    trend = trend_score(latest, ma5_latest, ma10_latest, ma30_latest)
    distribution = distribution_score(klines, turnover_percentile)
    status = status_from_scores(trend, turnover_percentile, distribution, ma_state)
    risk = classify_risk(distribution, ma_state)
    quant_score = max(0, min(100, int(turnover_percentile * 0.62 + (latest.get("amplitude") or 0) * 4 + abs(latest.get("pct_change") or 0) * 2)))
    overall = int(round(trend * 0.34 + turnover_percentile * 0.22 + (100 - distribution) * 0.22 + quant_score * 0.12 + 10))

    chart_points = []
    start = max(0, len(closes) - 80)
    for index in range(start, len(closes)):
        chart_points.append(
            {
                "date": klines[index]["date"],
                "close": closes[index],
                "ma5": ma5[index],
                "ma10": ma10[index],
                "ma30": ma30[index],
                "turnover_rate": klines[index]["turnover_rate"],
            }
        )

    latest_price = scaled_price(quote_data.get("f43")) or latest["close"]
    pct_change = scaled_percent(quote_data.get("f170"))
    if pct_change is None:
        pct_change = latest.get("pct_change")

    conclusion = build_conclusion(
        name=quote_data.get("f58") or kline_data.get("name") or code,
        ma_state=ma_state,
        turnover_percentile=turnover_percentile,
        turnover_ratio=turnover_ratio,
        distribution=distribution,
        risk=risk,
    )

    return {
        "code": quote_data.get("f57") or code,
        "name": quote_data.get("f58") or kline_data.get("name") or code,
        "industry": metadata.get("industry") or meta.get("industry", "待映射"),
        "board": metadata.get("board") or meta.get("board", "A股"),
        "concepts": metadata.get("concepts", []),
        "latest_price": latest_price,
        "pct_change": pct_change,
        "open": scaled_price(quote_data.get("f46")) or latest.get("open"),
        "high": scaled_price(quote_data.get("f44")) or latest.get("high"),
        "low": scaled_price(quote_data.get("f45")) or latest.get("low"),
        "previous_close": scaled_price(quote_data.get("f60")),
        "volume": quote_data.get("f47"),
        "amount": quote_data.get("f48"),
        "market_cap": quote_data.get("f116"),
        "turnover_rate": latest_turnover,
        "turnover_percentile": turnover_percentile,
        "turnover_ratio": round(turnover_ratio, 2),
        "ma": {
            "ma5": round(ma5_latest, 2) if ma5_latest else None,
            "ma10": round(ma10_latest, 2) if ma10_latest else None,
            "ma30": round(ma30_latest, 2) if ma30_latest else None,
        },
        "trend_score": trend,
        "turnover_score": int(round(turnover_percentile)),
        "quant_score": quant_score,
        "distribution_score": distribution,
        "risk": risk,
        "status": status,
        "overall_score": max(0, min(100, overall)),
        "ma_state": ma_state,
        "sector_alignment": "、".join(metadata.get("concepts") or []) or "待接入行业指数",
        "metadata_source": metadata.get("source", "fallback"),
        "confidence": "中" if len(klines) >= 120 else "低",
        "conclusion": conclusion,
        "chart": chart_points,
        "recent_klines": klines[-20:],
        "source": {
            "provider": "东方财富 push2 / push2his",
            "quote_url": quote_url(code),
            "kline_url": kline_url(code),
            "fetched_at": now_iso(),
            "latest_trade_date": latest["date"],
            "note": "行情数据来自公开网络接口；交易决策前应与交易软件或官方公告交叉核对。",
        },
    }


def get_stock_cached(code: str, meta: Optional[Dict[str, str]] = None, force: bool = False) -> Dict[str, Any]:
    meta = meta or {}
    now = time.time()
    with CACHE_LOCK:
        cached = STOCK_CACHE.get(code)
        if cached and not force and now - cached["time"] <= CACHE_TTL_SECONDS:
            return cached["stock"]
    stock = fetch_stock(code, meta)
    stock["pool"] = meta.get("pool", "核心自选")
    stock["watch_note"] = meta.get("note", "")
    with CACHE_LOCK:
        STOCK_CACHE[code] = {"time": now, "stock": stock}
    return stock


def fetch_watchlist_payload(force: bool = False) -> Dict[str, Any]:
    now = time.time()
    with CACHE_LOCK:
        cached = WATCHLIST_CACHE.get("payload")
        cached_time = float(WATCHLIST_CACHE.get("time") or 0)
        if cached and not force and now - cached_time <= CACHE_TTL_SECONDS:
            return cached

    items = read_watchlist()
    result: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=min(FETCH_WORKERS, max(1, len(items)))) as executor:
        futures = {executor.submit(get_stock_cached, item["code"], item, force): item for item in items}
        for future in as_completed(futures):
            item = futures[future]
            try:
                result.append(future.result())
            except Exception as exc:
                errors.append({"code": item["code"], "error": str(exc)})

    order = {item["code"]: index for index, item in enumerate(items)}
    result.sort(key=lambda stock: order.get(stock["code"], 9999))
    fallback_only = False
    if items and not result:
        fallback_only = True
        result = [
            {
                "code": item["code"],
                "name": item["code"],
                "industry": item.get("industry", "待映射"),
                "board": item.get("board", "A股"),
                "pool": item.get("pool", "核心自选"),
                "watch_note": item.get("note", ""),
                "latest_price": None,
                "pct_change": None,
                "open": None,
                "high": None,
                "low": None,
                "previous_close": None,
                "amount": None,
                "turnover_rate": None,
                "turnover_percentile": None,
                "turnover_ratio": None,
                "ma": {"ma5": None, "ma10": None, "ma30": None},
                "trend_score": None,
                "turnover_score": None,
                "risk": "待确认",
                "ma_state": "真实行情暂不可用",
                "confidence": "低",
                "conclusion": "真实行情接口暂时不可用，先保留自选股档案和复盘入口；交易前请在交易软件中交叉核对行情。",
                "chart": [],
                "recent_klines": [],
                "source": {
                    "provider": "自选股档案",
                    "fetched_at": now_iso(),
                    "latest_trade_date": "待确认",
                    "note": "行情接口失败时的自选股档案占位数据。",
                },
            }
            for item in items
        ]
    payload = {
        "ok": True,
        "stocks": result,
        "watchlist": items,
        "errors": errors,
        "source": {
            "provider": "自选股档案" if fallback_only else "东方财富 push2 / push2his",
            "fetched_at": now_iso(),
            "count": len(result),
            "scope": "用户自选股池",
            "mode": "fallback" if fallback_only else "live",
        },
    }
    with CACHE_LOCK:
        WATCHLIST_CACHE["time"] = now
        WATCHLIST_CACHE["payload"] = payload
    return payload


def build_conclusion(
    name: str,
    ma_state: str,
    turnover_percentile: float,
    turnover_ratio: float,
    distribution: int,
    risk: str,
) -> str:
    parts = [f"{name} 当前技术结构为“{ma_state}”。"]
    if turnover_percentile >= 85:
        parts.append(f"换手率处于自身历史高分位（约 {turnover_percentile}%），需要重点识别高换手后的承接质量。")
    elif turnover_percentile >= 65:
        parts.append(f"换手率高于常态（历史分位约 {turnover_percentile}%），说明筹码交换较活跃。")
    else:
        parts.append(f"换手率未进入极端区间（历史分位约 {turnover_percentile}%），短线拥挤度暂不高。")
    if turnover_ratio >= 2.5:
        parts.append(f"当日换手约为 20 日均值的 {turnover_ratio:.1f} 倍，需观察是否放量滞涨。")
    if distribution >= 70:
        parts.append("派发风险评分偏高，不宜追涨，应等待次日修复或重新站回关键均线。")
    elif "多头" in ma_state and risk != "高":
        parts.append("趋势结构较健康，更适合等待回踩确认，而不是情绪化追高。")
    else:
        parts.append("信号仍需确认，建议把反证条件写入复盘。")
    return "".join(parts)


def sanitize_filename(value: str) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", value.strip())
    return value[:120] or "未命名"


def ensure_vault() -> None:
    for folder in [
        OBSIDIAN_ROOT,
        OBSIDIAN_ROOT / "股票",
        OBSIDIAN_ROOT / "历史回顾",
        OBSIDIAN_ROOT / "操作记录",
        OBSIDIAN_ROOT / "策略假设",
        OBSIDIAN_ROOT / "风险案例",
        OBSIDIAN_ROOT / "数据快照",
        OBSIDIAN_ROOT / "知识图谱",
        OBSIDIAN_ROOT / "data",
    ]:
        folder.mkdir(parents=True, exist_ok=True)


def watchlist_path() -> Path:
    return OBSIDIAN_ROOT / "data" / "watchlist.json"


def default_watchlist() -> List[Dict[str, str]]:
    return []


def read_watchlist() -> List[Dict[str, str]]:
    ensure_vault()
    path = watchlist_path()
    if not path.exists():
        path.write_text(json.dumps(default_watchlist(), ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = default_watchlist()
    result = []
    seen = set()
    for item in data:
        code = str(item.get("code") or "").strip()
        if not re.fullmatch(r"\d{6}", code) or code in seen:
            continue
        seen.add(code)
        result.append(
            {
                "code": code,
                "industry": str(item.get("industry") or "待映射"),
                "board": str(item.get("board") or "A股"),
                "pool": str(item.get("pool") or "核心自选"),
                "note": str(item.get("note") or ""),
            }
        )
    return result


def write_watchlist(items: List[Dict[str, str]]) -> None:
    ensure_vault()
    watchlist_path().write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    with CACHE_LOCK:
        WATCHLIST_CACHE["time"] = 0.0
        WATCHLIST_CACHE["payload"] = None


def add_watchlist_item(payload: Dict[str, Any]) -> Dict[str, Any]:
    code = str(payload.get("code") or "").strip()
    if not re.fullmatch(r"\d{6}", code):
        raise ValueError("请输入 6 位 A 股代码")
    items = read_watchlist()
    if any(item["code"] == code for item in items):
        raise ValueError(f"{code} 已在自选股池中")
    meta = {
        "code": code,
        "industry": str(payload.get("industry") or "待映射"),
        "board": str(payload.get("board") or "A股"),
        "pool": str(payload.get("pool") or "核心自选"),
        "note": str(payload.get("note") or ""),
    }
    try:
        stock = get_stock_cached(code, meta, force=True)
    except Exception:
        stock = {
            "code": code,
            "name": code,
            "industry": meta["industry"],
            "board": meta["board"],
            "pool": meta["pool"],
            "watch_note": meta["note"],
            "latest_price": None,
            "pct_change": None,
            "ma_state": "真实行情暂不可用",
            "risk": "待确认",
            "confidence": "低",
            "conclusion": "已先创建自选股档案；行情恢复后会自动补充实时数据。",
            "source": {"provider": "自选股档案", "latest_trade_date": "待确认", "fetched_at": now_iso()},
        }
    meta["industry"] = meta["industry"] if meta["industry"] != "待映射" else stock.get("industry", "待映射")
    meta["board"] = meta["board"] if meta["board"] != "A股" else stock.get("board", "A股")
    items.append(meta)
    write_watchlist(items)
    stock_file = ensure_stock_note(stock)
    return {"ok": True, "item": meta, "stock": stock, "stock_path": str(stock_file)}


def delete_watchlist_item(code: str) -> Dict[str, Any]:
    if not re.fullmatch(r"\d{6}", code):
        raise ValueError("请输入 6 位 A 股代码")
    items = read_watchlist()
    next_items = [item for item in items if item["code"] != code]
    if len(next_items) == len(items):
        raise ValueError(f"{code} 不在自选股池中")
    write_watchlist(next_items)
    return {"ok": True, "code": code, "count": len(next_items)}


def stock_note_path(stock_code: str, stock_name: str) -> Path:
    return OBSIDIAN_ROOT / "股票" / f"{sanitize_filename(stock_code)}-{sanitize_filename(stock_name)}.md"


def ensure_stock_note(stock: Dict[str, Any]) -> Path:
    ensure_vault()
    stock_code = str(stock.get("code") or "unknown")
    stock_name = str(stock.get("name") or "未知股票")
    stock_file = stock_note_path(stock_code, stock_name)
    if not stock_file.exists():
        stock_file.write_text(
            (
                "---\n"
                f"code: {stock_code}\n"
                f"name: {stock_name}\n"
                "market: A股\n"
                f"industry: {stock.get('industry', '待映射')}\n"
                f"board: {stock.get('board', 'A股')}\n"
                f"pool: {stock.get('pool', '核心自选')}\n"
                "tags:\n"
                "  - stock/a-share\n"
                "  - behavior-profile\n"
                "---\n\n"
                f"# {stock_code} {stock_name}\n\n"
                "## 股票画像\n\n"
                "- 自选池：待维护\n"
                "- 关注原因：待维护\n"
                "- 主要交易假设：待维护\n"
                "- 关键风险：待维护\n\n"
                "## 每日复盘记录\n\n"
            ),
            encoding="utf-8",
        )
    return stock_file


def append_stock_review(stock_code: str, stock_name: str, review_date: str, summary: str, review_path: Path) -> Path:
    stock_file = ensure_stock_note({"code": stock_code, "name": stock_name})
    with stock_file.open("a", encoding="utf-8") as handle:
        handle.write(
            f"- {review_date}：{summary}。来源：[[{review_path.stem}]]\n"
        )
    return stock_file


def write_stock_daily_review(payload: Dict[str, Any]) -> Dict[str, Any]:
    ensure_vault()
    review_date = payload.get("date") or datetime.now().strftime("%Y-%m-%d")
    stock_code = sanitize_filename(str(payload.get("stock_code") or "unknown"))
    stock_name = sanitize_filename(str(payload.get("stock_name") or "未知股票"))
    analysis_focus = str(payload.get("analysis_focus") or "综合复盘").strip()
    technical_notes = str(payload.get("technical_notes") or "未填写").strip()
    volume_notes = str(payload.get("volume_notes") or "未填写").strip()
    fundamental_notes = str(payload.get("fundamental_notes") or "未填写").strip()
    risk_notes = str(payload.get("risk_notes") or "未填写").strip()
    plan_notes = str(payload.get("plan_notes") or "未填写").strip()
    ai_summary = str(payload.get("ai_summary") or "等待 AI 维度分析").strip()
    evaluation = str(payload.get("evaluation") or "等待研究结论").strip()
    quote_snapshot = payload.get("quote_snapshot") or {}
    metadata_service = StockMetadataService(DATA_ROOT)
    stock_metadata = metadata_service.get_stock_metadata(
        stock_code,
        fallback={
            "name": stock_name,
            "industry": payload.get("industry", "待映射"),
            "board": payload.get("board", "A股"),
            "concepts": payload.get("concepts", []),
        },
    )
    payload_concepts = payload.get("concepts") if isinstance(payload.get("concepts"), list) else []
    metadata_concepts = stock_metadata.get("concepts") or payload_concepts
    if not quote_snapshot.get("ma_state") and payload.get("ma_state"):
        quote_snapshot["ma_state"] = payload.get("ma_state")
    review_fields = {
        "analysis_focus": analysis_focus,
        "technical_notes": technical_notes,
        "volume_notes": volume_notes,
        "fundamental_notes": fundamental_notes,
        "risk_notes": risk_notes,
        "plan_notes": plan_notes,
        "ai_summary": ai_summary,
        "evaluation": evaluation,
    }
    knowledge_graph = ObsidianKnowledgeGraphService(OBSIDIAN_ROOT)
    graph_context = knowledge_graph.build_review_context(
        {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "industry": stock_metadata.get("industry") or payload.get("industry", "待映射"),
            "board": stock_metadata.get("board") or payload.get("board", "A股"),
            "concepts": metadata_concepts,
        },
        quote_snapshot,
        review_fields,
    )
    knowledge_graph.write_concept_notes(graph_context)
    ai_dialogue_summary = str(payload.get("ai_dialogue_summary") or "").strip()
    ai_dialogue = payload.get("ai_dialogue") or []
    dialogue_lines = []
    if isinstance(ai_dialogue, list):
        for item in ai_dialogue[-8:]:
            if not isinstance(item, dict):
                continue
            role = "我" if item.get("role") == "user" else "AI"
            content = str(item.get("content") or "").strip()
            if content:
                dialogue_lines.append(f"- **{role}**：{content}")

    stock_file = ensure_stock_note(
        {
            "code": stock_code,
            "name": stock_name,
            "industry": stock_metadata.get("industry") or payload.get("industry", "待映射"),
            "board": stock_metadata.get("board") or payload.get("board", "A股"),
            "pool": payload.get("pool", "核心自选"),
        }
    )
    block = (
        f"\n### {review_date} 多维度分析\n\n"
        f"- 分析重点：{analysis_focus}\n"
        f"- 收盘/最新价：{quote_snapshot.get('latest_price', '未知')}\n"
        f"- 涨跌幅：{quote_snapshot.get('pct_change', '未知')}\n"
        f"- 换手率：{quote_snapshot.get('turnover_rate', '未知')}\n"
        f"- 风险等级：{quote_snapshot.get('risk', '未知')}\n\n"
        "#### 技术结构\n\n"
        f"{technical_notes}\n\n"
        "#### 量能与换手\n\n"
        f"{volume_notes}\n\n"
        "#### 基本面与板块\n\n"
        f"{fundamental_notes}\n\n"
        "#### 风险与反证\n\n"
        f"{risk_notes}\n\n"
        "#### 观察计划\n\n"
        f"{plan_notes}\n\n"
        "> [!summary] 维度分析\n"
        f"> {ai_summary.replace(chr(10), chr(10) + '> ')}\n\n"
        "> [!check] 研究结论\n"
        f"> {evaluation.replace(chr(10), chr(10) + '> ')}\n"
    )
    graph_section = knowledge_graph.markdown_section(graph_context)
    if graph_section:
        block += f"\n{graph_section}\n"
    if ai_dialogue_summary:
        block += (
            "\n> [!note] AI 对话补充\n"
            f"> {ai_dialogue_summary.replace(chr(10), chr(10) + '> ')}\n"
        )
    if dialogue_lines:
        block += "\n#### AI 对话记录\n\n" + "\n".join(dialogue_lines) + "\n"

    with stock_file.open("a", encoding="utf-8") as handle:
        handle.write(block)

    daily_file = OBSIDIAN_ROOT / "操作记录" / f"{review_date}-{stock_code}-{stock_name}.md"
    daily_file.write_text(
        (
            "---\n"
            f"title: {review_date} {stock_code}-{stock_name} 多维度分析\n"
            f"date: {review_date}\n"
            f"stock: {stock_code}-{stock_name}\n"
            f"industry: {stock_metadata.get('industry') or payload.get('industry', '待映射')}\n"
            f"concepts: {', '.join(metadata_concepts)}\n"
            "review_type: stock_dimension_review\n"
            "tags:\n"
            "  - review/stock-daily\n"
            "  - trading-memory\n"
            "---\n\n"
            f"# {review_date} {stock_code} {stock_name} 多维度分析\n"
            f"{block}\n"
        ),
        encoding="utf-8",
    )
    return {
        "ok": True,
        "stock_path": str(stock_file),
        "daily_path": str(daily_file),
        "written_at": now_iso(),
    }


def write_daily_review(payload: Dict[str, Any]) -> Dict[str, Any]:
    ensure_vault()
    review_date = payload.get("date") or datetime.now().strftime("%Y-%m-%d")
    stock_code = sanitize_filename(str(payload.get("stock_code") or "unknown"))
    stock_name = sanitize_filename(str(payload.get("stock_name") or "未知股票"))
    markdown = str(payload.get("markdown") or "").strip()
    if not markdown:
        raise ValueError("markdown is required")

    filename = f"{review_date}-每日研究回顾.md"
    review_path = OBSIDIAN_ROOT / "历史回顾" / filename
    review_path.write_text(markdown + "\n", encoding="utf-8")

    success = str(payload.get("success_reason") or "未填写成功原因").strip()
    failure = str(payload.get("failure_reason") or "未填写失败原因").strip()
    summary = f"成功原因：{success}；失败原因：{failure}"
    stock_file = append_stock_review(stock_code, stock_name, review_date, summary, review_path)

    return {
        "ok": True,
        "vault_root": str(OBSIDIAN_ROOT),
        "review_path": str(review_path),
        "stock_path": str(stock_file),
        "written_at": now_iso(),
    }


def deepseek_dimension_prompt(stock: Dict[str, Any], review: Dict[str, Any]) -> List[Dict[str, str]]:
    system_prompt = (
        "你是一名严谨的A股股票研究助手，只做研究分析和风险提示，不承诺收益，不输出确定性买卖指令。"
        "你需要根据给定行情、技术指标、换手、行业板块和用户关注点，生成可写入长期复盘系统的分析。"
        "输出必须是严格JSON，不要包含Markdown围栏。字段必须包含："
        "technical_notes, volume_notes, fundamental_notes, risk_notes, plan_notes, dimension_analysis, research_conclusion。"
        "每个字段使用中文，务必具体、克制、可复盘。"
    )
    user_payload = {
        "task": "为当前股票自动填写多维度股票分析表单",
        "constraints": [
            "不要编造未提供的财务数据、公告或新闻。",
            "如果信息不足，要明确写出需要核验的外部信息。",
            "技术结构要结合价格、均线、趋势状态。",
            "量能与换手要结合成交额、换手率、换手分位和承接/抛压假设。",
            "基本面与板块只基于行业、板块、已知行情上下文做研究框架。",
            "风险与反证要写清什么情况会推翻当前判断。",
            "观察计划要给出下一步跟踪条件，而不是直接下买卖指令。",
        ],
        "stock": stock,
        "current_form": review,
    }
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, indent=2)},
    ]


def parse_deepseek_json(content: str) -> Dict[str, str]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)
    result = {}
    for key in [
        "technical_notes",
        "volume_notes",
        "fundamental_notes",
        "risk_notes",
        "plan_notes",
        "dimension_analysis",
        "research_conclusion",
    ]:
        result[key] = str(data.get(key) or "").strip()
    return result


def call_deepseek_dimension_analysis(payload: Dict[str, Any]) -> Dict[str, Any]:
    api_key = read_local_secret("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("DeepSeek API key is not configured. Set DEEPSEEK_API_KEY or create deepseek.local.json.")

    stock = payload.get("stock") or {}
    review = payload.get("review") or {}
    request_payload = {
        "model": os.environ.get("DEEPSEEK_MODEL", DEEPSEEK_MODEL),
        "messages": deepseek_dimension_prompt(stock, review),
        "temperature": 0.25,
        "max_tokens": 3000,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        f"{DEEPSEEK_API_BASE}/chat/completions",
        data=json.dumps(request_payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DeepSeek request failed: HTTP {exc.code} {detail}") from exc
    content = response_payload["choices"][0]["message"]["content"]
    analysis = parse_deepseek_json(content)
    return {
        "ok": True,
        "model": request_payload["model"],
        "analysis": analysis,
        "generated_at": now_iso(),
    }


def json_response(handler: SimpleHTTPRequestHandler, payload: Dict[str, Any], status: int = 200) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def read_uploaded_image(handler: SimpleHTTPRequestHandler) -> Dict[str, Any]:
    content_type = handler.headers.get("Content-Type", "")
    if not content_type.startswith("multipart/form-data"):
        raise ValueError("请使用 multipart/form-data 上传截图")
    try:
        import cgi

        form = cgi.FieldStorage(
            fp=handler.rfile,
            headers=handler.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": content_type,
            },
        )
        file_item = form["file"] if "file" in form else None
        if file_item is None or getattr(file_item, "file", None) is None:
            raise ValueError("file is required")
        image_bytes = file_item.file.read()
        mime_type = getattr(file_item, "type", None) or "image/jpeg"
        trade_date = form.getfirst("trade_date") or datetime.now().strftime("%Y-%m-%d")
        return {"image_bytes": image_bytes, "mime_type": mime_type, "trade_date": trade_date}
    except Exception as exc:
        if isinstance(exc, ValueError):
            raise
        raise ValueError(f"截图上传解析失败：{exc}") from exc


class AShareHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/health":
            json_response(
                self,
                {
                    "ok": True,
                    "time": now_iso(),
                    "obsidian_root": str(OBSIDIAN_ROOT),
                    "data_source": "东方财富 push2 / push2his",
                },
            )
            return
        if parsed.path == "/api/stock":
            query = urllib.parse.parse_qs(parsed.query)
            code = (query.get("code") or [""])[0]
            meta = next((item for item in read_watchlist() if item["code"] == code), {})
            try:
                force = (query.get("force") or ["0"])[0] == "1"
                json_response(self, {"ok": True, "stock": get_stock_cached(code, meta, force=force)})
            except Exception as exc:
                json_response(self, {"ok": False, "error": str(exc)}, status=502)
            return
        if parsed.path == "/api/watchlist":
            query = urllib.parse.parse_qs(parsed.query)
            force = (query.get("force") or ["0"])[0] == "1"
            payload = fetch_watchlist_payload(force=force)
            json_response(self, payload, status=200 if payload["ok"] else 502)
            return
        if parsed.path == "/api/trading/dashboard":
            query = urllib.parse.parse_qs(parsed.query)
            date_value = (query.get("date") or [datetime.now().strftime("%Y-%m-%d")])[0]
            services = trading_services()
            account_dashboard = services["account"].dashboard(date_value)
            trades = services["trade"].list_trades(date_value)
            json_response(
                self,
                {
                    "ok": True,
                    "success": True,
                    "date": date_value,
                    "account": account_dashboard,
                    "trades": trades,
                    "parse_drafts": services["trade"].list_parse_drafts("pending"),
                },
            )
            return
        if parsed.path == "/api/trading/capital-flows":
            services = trading_services()
            json_response(self, {"ok": True, "success": True, "flows": services["account"].list_capital_flows()})
            return
        if parsed.path == "/api/trading/account-snapshots":
            query = urllib.parse.parse_qs(parsed.query)
            date_value = (query.get("date") or [None])[0]
            services = trading_services()
            json_response(self, {"ok": True, "success": True, "snapshots": services["account"].list_account_snapshots(date_value)})
            return
        if parsed.path == "/api/trading/trades":
            query = urllib.parse.parse_qs(parsed.query)
            date_value = (query.get("date") or [None])[0]
            services = trading_services()
            json_response(self, {"ok": True, "success": True, "trades": services["trade"].list_trades(date_value)})
            return
        if parsed.path == "/api/trading/parse-drafts":
            services = trading_services()
            json_response(self, {"ok": True, "success": True, "drafts": services["trade"].list_parse_drafts()})
            return
        return super().do_GET()

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in {"/api/trading/parse/account-screenshot", "/api/trading/parse/trades-screenshot"}:
            try:
                upload = read_uploaded_image(self)
                services = trading_services()
                if parsed.path.endswith("account-screenshot"):
                    parsed_payload = services["vision"].parse_account_screenshot(upload["image_bytes"], upload["mime_type"])
                    draft = services["trade"].create_parse_draft("account_screenshot", upload["trade_date"], parsed_payload, [])
                else:
                    parsed_payload = services["vision"].parse_trades_screenshot(upload["image_bytes"], upload["mime_type"])
                    warnings = []
                    for trade in parsed_payload.get("trades") or []:
                        if not trade.get("stock_code") and trade.get("stock_name"):
                            match = services["stock_match"].match_name(trade["stock_name"])
                            trade["stock_match"] = match
                            if match.get("status") == "matched":
                                trade["stock_code"] = match.get("stock_code", "")
                            else:
                                warnings.append(f"{trade.get('stock_name')} 股票代码未唯一匹配")
                    draft = services["trade"].create_parse_draft("trades_screenshot", upload["trade_date"], parsed_payload, warnings)
                json_response(self, {"ok": True, "success": True, "draft": draft})
            except Exception as exc:
                json_response(self, {"ok": False, "success": False, "error": str(exc), "message": str(exc)}, status=400)
            return
        length = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            services = trading_services()
            if parsed.path == "/api/obsidian/daily-review":
                json_response(self, write_daily_review(payload))
                return
            if parsed.path == "/api/obsidian/stock-daily-review":
                json_response(self, write_stock_daily_review(payload))
                return
            if parsed.path == "/api/ai/dimension-analysis":
                json_response(self, call_deepseek_dimension_analysis(payload))
                return
            if parsed.path == "/api/watchlist":
                json_response(self, add_watchlist_item(payload))
                return
            if parsed.path == "/api/trading/capital-flows":
                json_response(self, {"ok": True, "success": True, "flow": services["account"].add_capital_flow(payload)})
                return
            if parsed.path == "/api/trading/account-snapshots":
                json_response(self, {"ok": True, "success": True, "snapshot": services["account"].add_account_snapshot(payload)})
                return
            if parsed.path == "/api/trading/trades":
                json_response(self, {"ok": True, "success": True, "trade": services["trade"].add_trade(payload)})
                return
            if parsed.path.startswith("/api/trading/parse-drafts/") and parsed.path.endswith("/confirm"):
                draft_id = parsed.path.split("/")[-2]
                result = services["trade"].confirm_draft(draft_id, payload)
                json_response(self, {"ok": True, "success": True, **result})
                return
            if parsed.path.startswith("/api/trading/parse-drafts/") and parsed.path.endswith("/reject"):
                draft_id = parsed.path.split("/")[-2]
                draft = services["trade"].reject_draft(draft_id)
                json_response(self, {"ok": True, "success": True, "draft": draft})
                return
            if parsed.path == "/api/trading/daily-review":
                result = services["obsidian"].write_daily_review(
                    payload.get("date") or datetime.now().strftime("%Y-%m-%d"),
                    payload.get("snapshot") or {},
                    payload.get("trades") or [],
                    payload.get("review") or {},
                )
                json_response(self, result)
                return
            if parsed.path == "/api/trading/insights/update":
                result = services["obsidian"].update_insight_index(payload.get("insight") or payload)
                json_response(self, result)
                return
            if parsed.path == "/api/trading/stock-match":
                result = services["stock_match"].match_name(str(payload.get("stock_name") or ""))
                json_response(self, {"ok": True, "success": True, "match": result})
                return
            json_response(self, {"ok": False, "error": "Not found"}, status=404)
        except Exception as exc:
            json_response(self, {"ok": False, "success": False, "error": str(exc), "message": str(exc)}, status=400)

    def do_DELETE(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/api/watchlist":
            json_response(self, {"ok": False, "error": "Not found"}, status=404)
            return
        query = urllib.parse.parse_qs(parsed.query)
        code = (query.get("code") or [""])[0]
        try:
            json_response(self, delete_watchlist_item(code))
        except Exception as exc:
            json_response(self, {"ok": False, "error": str(exc)}, status=400)

    def log_message(self, format: str, *args: Any) -> None:
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {format % args}")
        except OSError:
            pass


def main() -> None:
    ensure_vault()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), AShareHandler)
    try:
        print(f"A股研究台 running at http://127.0.0.1:{PORT}")
        print(f"Obsidian vault root: {OBSIDIAN_ROOT}")
    except OSError:
        pass
    server.serve_forever()


if __name__ == "__main__":
    main()
