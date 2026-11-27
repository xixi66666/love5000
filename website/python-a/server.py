"""A 股自选股 AI 研究台的本地 HTTP 后端。

用标准库 ``ThreadingHTTPServer`` 在 ``127.0.0.1:5174``（可由 ``PORT`` 覆盖）提供静态页面
与 ``/api/**`` JSON 接口，共四类能力：

- 自选股与行情：读取 Obsidian 里的 ``data/watchlist.json``，聚合东方财富 ``push2`` 实时
  行情与 ``push2his`` 前复权日 K，在本地算均线、换手分位、趋势/派发评分与结论文案；
- 研究数据：经 ``StockResearchService`` 汇总腾讯、东方财富、新浪、巨潮的估值、资金流、
  研报与公告，按小节返回并各自标记 ``success``；
- 交易台账与截图解析：账户/交易/资金流/草稿的 JSON 存储，截图走 ``vision`` 模型解析；
- 复盘与 AI：把多维度分析写入 Obsidian（股票笔记 + 当日复盘），AI 结果经统一模型网关
  转发，未走网关时才用 ``model.properties`` 的原配置直连。

模型与密钥只来自仓库根目录 ``model.properties``（通过 ``services/_model_properties.py``
读取），不读环境变量；``PORT``/``ASHARE_OBSIDIAN_ROOT`` 是仅有的运行期环境变量。

降级策略：每个上游请求都带超时与重试上限，单只股票或单个数据源失败只影响对应字段——
自选股列表退化成“档案占位”并标注来源模式，研究快照里缺失的小节整节省略，接口始终返回
可渲染的 JSON（``ok``/``success`` 如实反映状态），不因外部接口抖动让页面整体不可用。

并发与缓存：行情用 ``ThreadPoolExecutor`` 并行抓取，进程内缓存 180 秒；``STOCK_CACHE``
与 ``WATCHLIST_CACHE`` 由 ``CACHE_LOCK`` 保护，自选股写入后立即失效。
"""

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
from services.cninfo_announcement_provider import CninfoAnnouncementProvider
from services.eastmoney_research_provider import EastmoneyResearchProvider
from services.knowledge_graph_service import ObsidianKnowledgeGraphService
from services.obsidian_service import ObsidianTradingService
from services.research_provider import validate_stock_code
from services.sina_fund_flow_provider import SinaFundFlowProvider
from services.stock_match_service import StockMatchService
from services.stock_metadata_service import StockMetadataService
from services.stock_research_service import StockResearchService
from services.storage_service import JsonStore
from services.tencent_quote_provider import TencentQuoteProvider
from services.trade_service import TradeService
from services.vision_parse_service import VisionParseService
from services import _model_properties as model_properties


# 静态页面与 services 包所在目录；SimpleHTTPRequestHandler 以它为文档根。
ROOT = Path(__file__).resolve().parent
# Obsidian 写入根目录；ASHARE_OBSIDIAN_ROOT 可把它指向真实 vault。
OBSIDIAN_ROOT = Path(os.environ.get("ASHARE_OBSIDIAN_ROOT", ROOT / "obsidian-vault" / "A股AI")).resolve()
# 自选股、交易台账与元数据缓存等 JSON 数据的存放目录。
DATA_ROOT = OBSIDIAN_ROOT / "data"
# 监听端口；PORT 是仅有的运行期环境变量之一（模型配置只读 model.properties）。
PORT = int(os.environ.get("PORT", "5174"))
# 行情缓存有效期（秒）：覆盖页面轮询频率，同时控制上游请求量。
CACHE_TTL_SECONDS = 180
# 自选股并行抓取上限，避免一次刷新把上游打出限流。
FETCH_WORKERS = 6

# 早期硬编码自选池的占位；实际自选股由 data/watchlist.json 维护。
WATCHLIST = [
]

# 东方财富对缺少 Referer/UA 的请求会返回空数据，这里统一伪装浏览器。
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/",
}

# 单只股票行情缓存：code -> {"time", "stock"}。
STOCK_CACHE: Dict[str, Dict[str, Any]] = {}
# 整个自选股列表的缓存；time 为 0 表示已被写入操作置为失效。
WATCHLIST_CACHE: Dict[str, Any] = {"time": 0.0, "payload": None}
# 两个缓存字典的互斥锁；真正的抓取在锁外进行，慢请求不会阻塞其他线程。
CACHE_LOCK = Lock()


def build_stock_research_service() -> StockResearchService:
    """装配研究数据聚合服务。

    把四个数据源 provider（腾讯/东方财富/新浪/巨潮）与本地元数据服务一起注入
    ``StockResearchService``；provider 每次新建，方便测试替换，生产路径只在模块加载时
    构建一次（``STOCK_RESEARCH_SERVICE``）。

    Returns:
        可直接调用 ``build_snapshot``/``get_overview`` 等方法的聚合服务实例。
    """
    return StockResearchService(
        tencent_provider=TencentQuoteProvider(),
        eastmoney_provider=EastmoneyResearchProvider(),
        sina_provider=SinaFundFlowProvider(),
        cninfo_provider=CninfoAnnouncementProvider(),
        metadata_service=StockMetadataService(DATA_ROOT),
    )


# 模块加载时构建一次，复用各 provider 内部的连接与缓存状态。
STOCK_RESEARCH_SERVICE = build_stock_research_service()


class DataSourceError(RuntimeError):
    """上游行情/研究数据不可用或结构不符时抛出的异常。

    调用方统一按“该字段降级”处理：``fetch_watchlist_payload`` 收集成 ``errors``，
    ``/api/stock`` 映射成 502。内部堆栈与上游原文不会透给前端，避免把内部地址带出去。
    """
    pass


def now_iso() -> str:
    """当前本地时区的 ISO-8601 时间戳（秒级）。

    Returns:
        形如 ``2026-11-27T10:31:13+08:00`` 的字符串，写入响应与 Obsidian 元数据，
        便于跨天复盘时判断数据新鲜度。
    """
    return datetime.now().astimezone().isoformat(timespec="seconds")


def text_route(scope: str = "python-a"):
    """读取 ``model.properties`` 中该服务的原配置路由。

    Args:
        scope: 服务标识，对应 ``service.<scope>``；缺省为 ``python-a``。

    Returns:
        ``Route`` 或 ``None``；文件缺失、键缺失或模型 ID 为空都返回 ``None``，
        调用方据此提示“模型未配置”而不是抛异常。
    """
    return model_properties.ModelProperties.load().route(scope)


def vision_config() -> Dict[str, str]:
    """读取 ``vision.*`` 提供方配置，供截图解析使用。

    Returns:
        含 ``api_key``/``api_base``/``model`` 的字典。缺少 ``vision`` 提供方时返回空密钥与
        默认模型名，真正调用前的校验由 ``VisionParseService`` 负责，
        避免进程启动阶段就因配置缺失而退出。
    """
    provider = model_properties.ModelProperties.load().provider("vision")
    if provider is None:
        return {"api_key": "", "api_base": "", "model": "gpt-4o-mini"}
    return {
        "api_key": provider.api_key,
        "api_base": provider.base_url,
        "model": provider.option("model", "gpt-4o-mini"),
    }


def trading_services() -> Dict[str, Any]:
    """按请求装配交易相关服务集合。

    每次请求新建实例而不是全局复用：``JsonStore`` 以文件为单位读写、服务本身无状态，
    这样可以避免跨请求持有过期缓存或文件句柄。

    Returns:
        含 ``account``/``trade``/``stock_match``/``obsidian``/``metadata``/
        ``knowledge_graph``/``vision`` 七个服务实例的字典。
    """
    store = JsonStore(DATA_ROOT)
    vision = vision_config()
    return {
        "account": AccountService(store),
        "trade": TradeService(store),
        "stock_match": StockMatchService(store, seed_rows=read_watchlist()),
        "obsidian": ObsidianTradingService(OBSIDIAN_ROOT),
        "metadata": StockMetadataService(DATA_ROOT),
        "knowledge_graph": ObsidianKnowledgeGraphService(OBSIDIAN_ROOT),
        "vision": VisionParseService(
            api_key=vision["api_key"],
            api_base=vision["api_base"],
            model=vision["model"],
        ),
    }


def secid_for_code(code: str) -> str:
    """把 6 位 A 股代码转换成东方财富的 ``secid``（``市场.代码``）。

    Args:
        code: 6 位数字代码，允许首尾空白。

    Returns:
        ``1.<code>`` 表示沪市（6/9 开头，含科创板与 B 股），``0.<code>`` 表示深市。

    Raises:
        ValueError: 代码不是 6 位数字。
    """
    code = code.strip()
    if not re.fullmatch(r"\d{6}", code):
        raise ValueError(f"Invalid A-share code: {code}")
    market = "1" if code.startswith(("6", "9")) else "0"
    return f"{market}.{code}"


def eastmoney_json(url: str) -> Dict[str, Any]:
    """请求东方财富接口并返回解析后的 JSON。

    优先走 ``curl.exe``：部分 Windows 环境里 urllib 会因 TLS/代理差异被对端直接断开，
    而 curl 自带 ``--retry`` 与 ``--max-time`` 控制。curl 不可用或返回非预期结构时回退
    urllib，最多两次退避重试；两种方式都失败才抛 ``DataSourceError``，由上层把该字段
    降级成“不可用”，不影响页面其他部分。

    Args:
        url: 已带完整查询串的东方财富接口地址。

    Returns:
        顶层为 dict 的响应体，且 ``rc`` 为 0/缺失、``data`` 非空。

    Raises:
        DataSourceError: 全部传输方式失败，或响应缺少 ``data``、``rc`` 非 0。
    """
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

    # curl 分支的任何异常（命令缺失、超时、结构不符）都吞掉，改走标准库重试。
    request = urllib.request.Request(url, headers=HTTP_HEADERS)
    last_error: Optional[BaseException] = None
    # 上游偶发 RemoteDisconnected，最多重试两次且间隔递增；仍失败则整体降级。
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
    """把东方财富的定点价格（×100 的整数）换算成元。

    ``-100000`` 及以下是对端的“无数据/停牌”哨兵值，按缺失处理，避免出现 -1000 元的荒谬价格。

    Args:
        value: 上游原始值，可能是字符串、数字或 ``-``。

    Returns:
        保留两位小数的价格；缺失或非法时返回 ``None``。
    """
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
    """把东方财富的定点百分比（×100 的整数）换算成百分数。

    ``abs(value) > 100000`` 视为哨兵值（停牌或异常放大），按缺失处理。

    Args:
        value: 上游原始值。

    Returns:
        保留两位小数的百分比；缺失或越界时返回 ``None``。
    """
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
    """把上游原始值转成 ``float``，可选四舍五入。

    Args:
        value: 可能是数字、数字字符串、``-`` 或 ``None``。
        digits: 保留小数位；``None`` 表示不舍入。

    Returns:
        有限浮点数；非法值以及 NaN/Inf 返回 ``None``——K 线里混入 NaN 会污染均线与评分。
    """
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
    """算术平均；空序列返回 ``None``，避免调用方处理 ``ZeroDivisionError``。"""
    values = list(values)
    return sum(values) / len(values) if values else None


def moving_average(values: List[float], window: int) -> List[Optional[float]]:
    """按窗口计算移动平均，返回与入参等长的列表。

    前 ``window - 1`` 个位置数据不足，填 ``None`` 而不是用数据起点截断，这样下标与 K 线
    一一对应，图表点位和评分都不会错位。

    Args:
        values: 收盘价序列，按时间升序。
        window: 窗口长度，例如 5/10/30。

    Returns:
        长度等于 ``values`` 的列表，不足窗口处为 ``None``。
    """
    result: List[Optional[float]] = []
    for index in range(len(values)):
        if index + 1 < window:
            result.append(None)
            continue
        result.append(round(sum(values[index - window + 1 : index + 1]) / window, 4))
    return result


def percentile_rank(values: List[float], current: float) -> float:
    """计算 ``current`` 在历史序列中的分位（0-100，越大越接近历史高位）。

    用 ``<=`` 计数，等于当前值的样本也算在内；空序列返回 0.0，调用方无需判空。
    """
    if not values:
        return 0.0
    less_or_equal = sum(1 for value in values if value <= current)
    return round(less_or_equal / len(values) * 100, 1)


def parse_kline(raw: str) -> Dict[str, Any]:
    """解析东方财富 K 线的一行逗号分隔字符串。

    字段顺序固定为 ``日期,开,收,高,低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率``
    （对应请求的 ``fields2=f51..f61``）。上游不返回字段名，只能按位置取值，
    字段不足或缺失时由调用方（``fetch_stock``）统一降级。

    Args:
        raw: 形如 ``2026-11-26,10.01,10.20,...`` 的单行字符串。

    Returns:
        含 ``date`` 与 10 个数值字段的字典；无法转换的字段为 ``None``。
    """
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
    """把派发评分与均线状态映射成风险等级（低/中/高）。

    阈值沿用复盘口径：派发分 ≥72 或跌破 30 日线判“高”，≥45 或跌破 10 日线判“中”，
    其余为“低”。分档只用于展示与排序，不构成操作建议。
    """
    if distribution_score >= 72 or "跌破30日" in risk_text:
        return "高"
    if distribution_score >= 45 or "跌破10日" in risk_text:
        return "中"
    return "低"


def trend_status(latest: Dict[str, Any], ma5: Optional[float], ma10: Optional[float], ma30: Optional[float]) -> str:
    """根据收盘价与 MA5/MA10/MA30 的相对位置给出趋势状态文案。

    Returns:
        ``多头排列``/``跌破30日``/``跌破10日``/``震荡修复``/``等待确认``；
        任一均线缺失时只返回“等待确认”，避免用不足 30 根 K 线的样本下结论。
    """
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
    """给趋势结构打分（0-100，基准 50）。

    加分项：站上各条均线、短均线位于长均线之上、当日上涨；涨幅贡献封顶 8 分，
    防止单日大涨把评分直接拉满。返回值截断到 0-100。
    """
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
    """估算高位派发风险评分（0-100）。

    三个维度：收盘价在近 60 日高点区间中的位置（越靠上越危险）、换手率历史分位、
    当日上影线占振幅的比例；再补两条“放量滞涨 / 放量收阴”的经验规则。

    Args:
        kline: 按时间升序的 K 线，至少 1 条。
        turnover_percentile: 最新换手率的历史分位（0-100）。

    Returns:
        0-100 的整数评分，越大越像派发。
    """
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
    """把评分与均线状态汇总成一句标签。

    判定顺序即优先级：先排除派发与诱多，再看均线破位，最后才给出低吸/接力/观察候选，
    保证互相矛盾的信号按保守顺序裁决。
    """
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
    """构造单只股票的实时行情接口地址（``push2``）。

    ``f43/f44/f45/f46/f47/f48`` 为最新价/最高/最低/今开/成交量/成交额，``f57/f58`` 为代码
    与名称，``f60`` 为昨收，``f116`` 为总市值，``f168`` 为换手率，``f170`` 为涨跌幅；
    ``f85``（量比）与 ``f292``（交易状态）目前只请求不使用，保留给后续扩展。
    所有数值都按定点整数返回，需用 ``scaled_price``/``scaled_percent`` 还原。
    """
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
    """构造日 K 线接口地址（``push2his``）。

    ``klt=101`` 为日线，``fqt=1`` 为前复权（保证均线连续），起始日期固定在 2024-01-01，
    足够覆盖 MA30 与 60 日分布区间；结束日期取远景值，由上游返回最新一根。
    """
    fields1 = "f1,f2,f3,f4,f5,f6"
    fields2 = "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
    return (
        "https://push2his.eastmoney.com/api/qt/stock/kline/get?"
        f"secid={secid_for_code(code)}&fields1={fields1}&fields2={fields2}"
        "&klt=101&fqt=1&beg=20240101&end=20500101"
    )


def fetch_stock(code: str, meta: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """抓取并计算单只股票的完整研究指标。

    两次上游请求（实时行情 + 日 K），之后全部在本地完成：MA5/10/30、换手分位、
    趋势/派发/量化评分、综合分、图表点位与结论文案。

    Args:
        code: 6 位 A 股代码。
        meta: 自选股档案（industry/board/pool/note），用于元数据缺失时兜底。

    Returns:
        行情字典：价格与量能、均线、各项评分、风险等级、结论文案、最近 80 个图表点、
        最近 20 根 K 线，以及 ``source`` 溯源信息（含两个上游 URL 与抓取时间）。

    Raises:
        DataSourceError: 东方财富不可用，或有效 K 线不足 35 根——无法稳定算出 MA30 时
            宁可让该股票整体降级，也不返回残缺指标。
    """
    meta = meta or {}
    metadata = StockMetadataService(DATA_ROOT).get_stock_metadata(code, fallback=meta)
    quote_data = eastmoney_json(quote_url(code))["data"]
    kline_data = eastmoney_json(kline_url(code))["data"]
    klines = [parse_kline(raw) for raw in kline_data.get("klines", [])]
    # 少于 35 根既算不出稳定 MA30，也没有足够样本算换手分位，直接按数据不足处理。
    if len(klines) < 35:
        raise DataSourceError(f"Not enough kline data for {code}")

    # 均线只基于非空收盘价；正常数据下该列表与 klines 等长，缺失值不会污染均值。
    closes = [item["close"] for item in klines if item["close"] is not None]
    ma5 = moving_average(closes, 5)
    ma10 = moving_average(closes, 10)
    ma30 = moving_average(closes, 30)
    latest = klines[-1]
    ma5_latest = ma5[-1]
    ma10_latest = ma10[-1]
    ma30_latest = ma30[-1]
    # 换手分位取最近约一年（250 个交易日）样本，过长历史会稀释当前拥挤度。
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
    # 短线拥挤度近似：换手分位为主，振幅与涨跌幅为辅，只用于排序参考。
    quant_score = max(0, min(100, int(turnover_percentile * 0.62 + (latest.get("amplitude") or 0) * 4 + abs(latest.get("pct_change") or 0) * 2)))
    # 综合分＝趋势 34%、换手 22%、派发反向 22%、量化 12%，另加 10 分基线。
    overall = int(round(trend * 0.34 + turnover_percentile * 0.22 + (100 - distribution) * 0.22 + quant_score * 0.12 + 10))

    # 图表只回传最近 80 个点，控制响应体积与前端渲染成本。
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
    """带进程内缓存地获取单只股票行情。

    缓存键只有 ``code``：命中时直接返回缓存里那份 ``stock``（其中 ``pool``/``watch_note``
    是填充缓存时写入的），因此修改自选股备注后需要 ``force=True`` 或等缓存过期才会体现在
    行情响应里。

    Args:
        code: 6 位 A 股代码。
        meta: 自选股档案，可空。
        force: ``True`` 时跳过缓存（手动刷新、新增自选股时使用）。

    Returns:
        行情字典，额外带 ``pool`` 与 ``watch_note``。

    Raises:
        DataSourceError: 缓存未命中且上游抓取失败；失败结果不会写入缓存。
    """
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
    """并行抓取整个自选股列表，单只失败只记入 ``errors``。

    Args:
        force: ``True`` 时同时绕过列表缓存与单只缓存（页面“刷新”按钮）。

    Returns:
        ``{"ok": True, "stocks": [...], "watchlist": [...], "errors": [...], "source": {...}}``。
        若所有股票都抓取失败，会退化成“档案占位”列表并把 ``source.mode`` 标成 ``fallback``，
        保证页面仍能展示自选池并给出可读说明。
    """
    now = time.time()
    with CACHE_LOCK:
        cached = WATCHLIST_CACHE.get("payload")
        cached_time = float(WATCHLIST_CACHE.get("time") or 0)
        if cached and not force and now - cached_time <= CACHE_TTL_SECONDS:
            return cached

    items = read_watchlist()
    result: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    # 线程数不超过自选股数量；单只股票的异常在 future.result() 处收集，不中断其余抓取。
    with ThreadPoolExecutor(max_workers=min(FETCH_WORKERS, max(1, len(items)))) as executor:
        futures = {executor.submit(get_stock_cached, item["code"], item, force): item for item in items}
        for future in as_completed(futures):
            item = futures[future]
            try:
                result.append(future.result())
            except Exception as exc:
                errors.append({"code": item["code"], "error": str(exc)})

    # 并行完成顺序不可控，按自选池原顺序重排后再返回。
    order = {item["code"]: index for index, item in enumerate(items)}
    result.sort(key=lambda stock: order.get(stock["code"], 9999))
    fallback_only = False
    # 全部失败时给出档案占位，页面仍有内容，并在 source.mode 里如实标注降级。
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
    """生成一段可读的中文结论文案（页面展示与复盘共用）。

    Args:
        name: 股票名称。
        ma_state: ``trend_status`` 给出的均线状态。
        turnover_percentile: 换手率历史分位。
        turnover_ratio: 当日换手 / 20 日均换手。
        distribution: 派发评分。
        risk: 风险等级。

    Returns:
        由 3-4 句组成的结论文本；只描述研究观察与反证条件，不含买卖指令。
    """
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
    """把任意文本清洗成可安全落盘的 Windows 文件名片段。

    把 ``<>:"/\|?*`` 与控制字符替换成 ``-``，并截断到 120 字符，
    防止生成非法路径或超长文件名；清洗后为空时回退为“未命名”。
    """
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", value.strip())
    return value[:120] or "未命名"


def ensure_vault() -> None:
    """确保 Obsidian 目录骨架存在（幂等）。

    ``exist_ok=True`` 让并发请求同时启动时不会因为“目录已存在”而失败；
    这里的目录清单与各处写入位置一一对应，新增写入目录时要同步补上。
    """
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
    """自选股档案文件位置：``<vault>/data/watchlist.json``。"""
    return OBSIDIAN_ROOT / "data" / "watchlist.json"


def default_watchlist() -> List[Dict[str, str]]:
    """自选股默认值：空池，由用户在前端维护。"""
    return []


def read_watchlist() -> List[Dict[str, str]]:
    """读取自选股档案，并做去重与字段归一化。

    文件缺失时先写入默认空池；JSON 损坏时按空池处理而不抛异常（用户手改坏文件不应该让
    整个页面打不开）。只保留 6 位数字代码，重复代码只保留首次出现的一条。

    Returns:
        列表，每项含 ``code``/``industry``/``board``/``pool``/``note``，缺失字段用默认值补齐。
    """
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
    """整体覆盖写入自选股档案，并让列表缓存立即失效。

    Args:
        items: 已归一化的自选股列表。
    """
    ensure_vault()
    watchlist_path().write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    # 用 time=0 让下一次读取必然重新抓取，同时保持缓存结构不变，读取方无需判空。
    with CACHE_LOCK:
        WATCHLIST_CACHE["time"] = 0.0
        WATCHLIST_CACHE["payload"] = None


def add_watchlist_item(payload: Dict[str, Any]) -> Dict[str, Any]:
    """新增一只自选股：校验代码、预抓行情、写档案并建股票笔记。

    行情抓取失败不阻断新增——先把档案落盘，等上游恢复后行情会自动补上。

    Args:
        payload: 请求体；``code`` 必填，``industry``/``board``/``pool``/``note`` 可选。

    Returns:
        ``{"ok": True, "item", "stock", "stock_path"}``，``stock_path`` 为 Obsidian 笔记路径。

    Raises:
        ValueError: 代码不是 6 位数字，或该代码已在自选池中。
    """
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
    # 先按真实行情补全行业/板块；上游异常时退化为占位档案，不阻断新增。
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
    # 用户没填的行业/板块用行情接口推断值补齐，避免笔记里全是“待映射”。
    meta["industry"] = meta["industry"] if meta["industry"] != "待映射" else stock.get("industry", "待映射")
    meta["board"] = meta["board"] if meta["board"] != "A股" else stock.get("board", "A股")
    items.append(meta)
    write_watchlist(items)
    stock_file = ensure_stock_note(stock)
    return {"ok": True, "item": meta, "stock": stock, "stock_path": str(stock_file)}


def delete_watchlist_item(code: str) -> Dict[str, Any]:
    """删除一只自选股。

    Args:
        code: 6 位 A 股代码。

    Returns:
        ``{"ok": True, "code", "count"}``，``count`` 为删除后的剩余数量。

    Raises:
        ValueError: 代码格式非法，或该代码不在自选池中。
    """
    if not re.fullmatch(r"\d{6}", code):
        raise ValueError("请输入 6 位 A 股代码")
    items = read_watchlist()
    next_items = [item for item in items if item["code"] != code]
    if len(next_items) == len(items):
        raise ValueError(f"{code} 不在自选股池中")
    write_watchlist(next_items)
    return {"ok": True, "code": code, "count": len(next_items)}


def stock_note_path(stock_code: str, stock_name: str) -> Path:
    """股票笔记路径：``<vault>/股票/<code>-<name>.md``，两段都做文件名清洗。"""
    return OBSIDIAN_ROOT / "股票" / f"{sanitize_filename(stock_code)}-{sanitize_filename(stock_name)}.md"


def ensure_stock_note(stock: Dict[str, Any]) -> Path:
    """确保单只股票的笔记存在并返回其路径。

    缺少时用固定骨架（YAML front matter + “股票画像”提纲）新建；已存在则原样返回，
    不覆盖用户手写内容，只由 ``append_stock_review`` 追加。

    Args:
        stock: 含 ``code``/``name`` 及可选 industry/board/pool 的字典。

    Returns:
        笔记的绝对路径。
    """
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
    """把一条复盘摘要追加到股票笔记底部，并双链回每日复盘文件。

    Args:
        stock_code: 股票代码，用于定位（缺失时新建）笔记。
        stock_name: 股票名称。
        review_date: 复盘日期，``YYYY-MM-DD``。
        summary: 一行摘要。
        review_path: 当日复盘 Markdown 路径，用其文件名主干生成 ``[[双链]]``。

    Returns:
        被追加的股票笔记路径。
    """
    stock_file = ensure_stock_note({"code": stock_code, "name": stock_name})
    # 一行一条复盘摘要，并用双链指回当天的历史回顾文件。
    with stock_file.open("a", encoding="utf-8") as handle:
        handle.write(
            f"- {review_date}：{summary}。来源：[[{review_path.stem}]]\n"
        )
    return stock_file


def provider_display_name(provider: Any) -> str:
    """把上游 provider 标识翻译成中文展示名，未知标识原样返回。"""
    names = {
        "tencent": "腾讯财经",
        "eastmoney": "东方财富",
        "sina": "新浪财经",
        "cninfo": "巨潮资讯",
        "szse": "深交所",
        "tushare": "Tushare",
        "fallback": "本地档案",
        "local": "本地档案",
    }
    value = str(provider or "未知来源")
    return names.get(value, value)


def research_snapshot_markdown(snapshot: Dict[str, Any]) -> str:
    """把研究数据快照渲染成 Markdown 片段（写入 Obsidian 复盘）。

    逐个小节先判断 ``success`` 再输出，缺失的数据源整节省略——复盘里不出现空表格或
    “未知”占位行；末尾固定附一条数据来源与交叉核验提示。

    Args:
        snapshot: ``StockResearchService.build_snapshot`` 返回的结构。

    Returns:
        Markdown 文本；快照为空时返回空串，调用方据空串跳过拼接。
    """
    if not isinstance(snapshot, dict) or not snapshot:
        return ""
    lines = ["#### 研究数据快照", ""]

    overview = snapshot.get("overview") or {}
    valuation = overview.get("valuation") or {}
    if valuation.get("success"):
        lines.extend(
            [
                "- 估值来源：{} · {}".format(
                    provider_display_name(valuation.get("provider")), valuation.get("data_date") or "时间待确认"
                ),
                "- PE(TTM)：{}；PB：{}；总市值：{} 亿元；流通市值：{} 亿元".format(
                    valuation.get("pe_ttm", "未知"),
                    valuation.get("pb", "未知"),
                    valuation.get("market_cap_yi", "未知"),
                    valuation.get("float_market_cap_yi", "未知"),
                ),
            ]
        )
    metadata = overview.get("metadata") or {}
    if metadata.get("success"):
        concepts = "、".join(str(item) for item in (metadata.get("concepts") or [])[:8]) or "未提供"
        lines.append(
            "- 行业概念：{}；{}（{}）".format(
                metadata.get("industry") or "待映射",
                concepts,
                provider_display_name(metadata.get("provider")),
            )
        )

    capital = snapshot.get("capital") or {}
    fund_flow = capital.get("fund_flow") or {}
    if fund_flow.get("success"):
        lines.append(
            "- 资金流：近 5 日{}，近 20 日{}（{} · {}）".format(
                fund_flow.get("five_day_direction") or "待确认",
                fund_flow.get("twenty_day_direction") or "待确认",
                provider_display_name(fund_flow.get("provider")),
                fund_flow.get("data_date") or "时间待确认",
            )
        )
    margin = capital.get("margin") or {}
    if margin.get("success"):
        lines.append(
            "- 融资余额：{}，较上一期变化 {}（{} · {}）".format(
                margin.get("latest_balance", "未知"),
                margin.get("balance_change", "未知"),
                provider_display_name(margin.get("provider")),
                margin.get("data_date") or "时间待确认",
            )
        )
    shareholders = capital.get("shareholders") or {}
    if shareholders.get("success"):
        lines.append(
            "- 股东户数：{}，环比 {}%（{} · {}）".format(
                shareholders.get("holder_count", "未知"),
                shareholders.get("change_ratio", "未知"),
                provider_display_name(shareholders.get("provider")),
                shareholders.get("data_date") or "时间待确认",
            )
        )
    lockups = capital.get("lockups") or {}
    if lockups.get("success"):
        upcoming = lockups.get("upcoming") or []
        lines.append(
            "- 未来 90 天解禁：{} 条（{} · {}）".format(
                len(upcoming),
                provider_display_name(lockups.get("provider")),
                lockups.get("data_date") or "时间待确认",
            )
        )

    events = snapshot.get("events") or {}
    reports = events.get("reports") or {}
    if reports.get("success") and reports.get("items"):
        titles = "；".join(str(item.get("title") or "") for item in reports["items"][:5] if item.get("title"))
        lines.append(
            "- 最新研报：{}（{} · {}）".format(
                titles,
                provider_display_name(reports.get("provider")),
                reports.get("data_date") or "时间待确认",
            )
        )
    announcements = events.get("announcements") or {}
    if announcements.get("success") and announcements.get("items"):
        titles = "；".join(
            str(item.get("title") or "") for item in announcements["items"][:5] if item.get("title")
        )
        lines.append(
            "- 最新公告：{}（{} · {}）".format(
                titles,
                provider_display_name(announcements.get("provider")),
                announcements.get("data_date") or "时间待确认",
            )
        )
    lines.extend(["", "> 数据来自公开网络接口，仅用于研究辅助；交易前请与交易软件和官方公告交叉核验。"])
    return "\n".join(lines)


def write_stock_daily_review(payload: Dict[str, Any]) -> Dict[str, Any]:
    """写入单只股票的多维度分析：追加股票笔记 + 生成当日复盘文件。

    同时把知识图谱概念笔记、研究快照与 AI 对话摘录落盘，是“AI 分析 → 长期记忆”的主入口。

    Args:
        payload: 前端表单与 AI 结果；常用键为 ``date``/``stock_code``/``stock_name``/
            各维度笔记文本/``ai_summary``/``evaluation``/``quote_snapshot``/
            ``research_snapshot``/``ai_dialogue``。

    Returns:
        ``{"ok": True, "stock_path", "daily_path", "written_at"}``。

    Notes:
        所有文本都先 ``str(...).strip()`` 并给默认值，缺字段只会写入“未填写”，不会抛异常；
        两个文件分别写入、没有事务，第二个文件失败时第一个文件已落盘（调用方转成 400）。
    """
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
    research_snapshot = payload.get("research_snapshot") or {}
    # 前端没带快照时按需现抓；研究服务异常只让该小节缺失，不阻断复盘写入。
    if not research_snapshot and re.fullmatch(r"\d{6}", stock_code):
        try:
            research_snapshot = STOCK_RESEARCH_SERVICE.build_snapshot(stock_code, load_missing=False)
        except Exception:
            research_snapshot = {}
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
    # 复盘块只用 Markdown；多行 AI 文本逐行补 ">" 才能保持 callout 结构。
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
    research_section = research_snapshot_markdown(research_snapshot)
    if research_section:
        block += "\n{}\n".format(research_section)
    if graph_section:
        block += f"\n{graph_section}\n"
    if ai_dialogue_summary:
        block += (
            "\n> [!note] AI 对话补充\n"
            f"> {ai_dialogue_summary.replace(chr(10), chr(10) + '> ')}\n"
        )
    if dialogue_lines:
        block += "\n#### AI 对话记录\n\n" + "\n".join(dialogue_lines) + "\n"

    # 追加写入：同一只股票的历次分析都保留，不覆盖用户已有内容。
    with stock_file.open("a", encoding="utf-8") as handle:
        handle.write(block)

    # 当日复盘单独成文，便于在 Obsidian 里按日期检索，并与股票笔记互链。
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
    """写入“每日研究回顾”：保存 Markdown 原文，并把摘要追加进股票笔记。

    Args:
        payload: ``markdown`` 必填；``date``/``stock_code``/``stock_name``/
            ``success_reason``/``failure_reason`` 可选。

    Returns:
        ``{"ok": True, "vault_root", "review_path", "stock_path", "written_at"}``。

    Raises:
        ValueError: ``markdown`` 为空，避免生成空复盘文件。
    """
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


def deepseek_dimension_prompt(
    stock: Dict[str, Any],
    review: Dict[str, Any],
    research_snapshot: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    """构造维度分析的对话消息（system 约束 + user JSON 载荷）。

    system 固定要求严格 JSON 且不承诺收益；user 把行情、当前表单和研究快照序列化进去，
    让模型只基于已提供的事实作答，减少编造公告或财务数据的空间。

    Args:
        stock: 行情/指标字典。
        review: 当前表单里已填写的内容。
        research_snapshot: 研究快照，可为空字典。

    Returns:
        ``[{"role": "system", ...}, {"role": "user", ...}]`` 两条消息。
    """
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
        "research_snapshot": research_snapshot or {},
    }
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, indent=2)},
    ]


def parse_deepseek_json(content: str) -> Dict[str, str]:
    """从模型输出里解析维度分析 JSON。

    模型偶尔会带上 Markdown 代码围栏，这里先剥壳再解析；七个字段统一转成去空白字符串，
    缺字段补空串，避免前端因为少一个键就整块渲染失败。

    Args:
        content: 模型返回的 ``choices[0].message.content``。

    Returns:
        七个键的字符串字典（技术/量能/基本面/风险/计划/维度分析/研究结论）。

    Raises:
        json.JSONDecodeError: 输出不是合法 JSON，由调用方转成可读提示。
    """
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
    """调用文本模型完成多维度分析并返回结构化结果。

    优先走统一模型网关（``model_hub.try_chat``）：返回 ``None`` 表示网关明确要求使用服务
    原配置，此时才读取 ``model.properties`` 的密钥直连提供方；网关报错不会静默改道，
    避免一次可能已计费的请求被重放。

    Args:
        payload: ``stock``/``review``/``research_snapshot``/``stock_code``。

    Returns:
        ``{"ok": True, "model", "analysis", "research_snapshot", "generated_at"}``。

    Raises:
        ValueError: 既没有统一路由、也没有原配置的模型与密钥时，提示去 ``model.properties`` 配置。
    """
    # 延迟导入：model_hub 在导入期读取模型配置，放函数内可避免启动阶段直接失败。
    from services import model_hub
    stock = payload.get("stock") or {}
    review = payload.get("review") or {}
    research_snapshot = payload.get("research_snapshot") or {}
    stock_code = str(stock.get("code") or payload.get("stock_code") or "").strip()
    if not research_snapshot and re.fullmatch(r"\d{6}", stock_code):
        research_snapshot = STOCK_RESEARCH_SERVICE.build_snapshot(stock_code, load_missing=True)
    route = text_route("python-a")
    request_payload = {
        "model": route.model_id if route else "",
        "messages": deepseek_dimension_prompt(stock, review, research_snapshot),
        "temperature": 0.25,
        "max_tokens": 3000,
        "response_format": {"type": "json_object"},
    }
    # 只有网关明确返回 204（None）才允许回退原配置；超时或 HTTP 错误直接抛出，避免重复计费。
    response_payload = model_hub.try_chat(request_payload)
    if response_payload is None:
        if route is None or not route.provider.api_key:
            raise ValueError("模型未配置：请在项目根目录 model.properties 填写 service.python-a 与对应 api-key。")
        response_payload = model_hub.native_chat(
            f"{route.provider.base_url}/chat/completions", route.provider.api_key, request_payload, timeout=90)
    content = response_payload["choices"][0]["message"]["content"]
    analysis = parse_deepseek_json(content)
    return {
        "ok": True,
        "model": response_payload.get("model", request_payload["model"]),
        "analysis": analysis,
        "research_snapshot": research_snapshot,
        "generated_at": now_iso(),
    }


# 研究数据路径：/api/stocks/<6 位代码>/research/{overview|capital|events}。
RESEARCH_ROUTE_PATTERN = re.compile(r"^/api/stocks/(\d{6})/research/(overview|capital|events)$")


def parse_research_route(path: str) -> Optional[tuple]:
    """解析研究数据接口路径。

    Args:
        path: 去掉查询串的 URL 路径。

    Returns:
        ``(code, section)`` 元组；路径不匹配时返回 ``None``。
    """
    match = RESEARCH_ROUTE_PATTERN.fullmatch(str(path or ""))
    if not match:
        return None
    return match.group(1), match.group(2)


def get_research_response(
    path: str,
    query_string: str,
    service: Optional[StockResearchService] = None,
) -> Dict[str, Any]:
    """执行研究数据接口，并把查询参数转成服务调用参数。

    Args:
        path: 请求路径，用于解析股票代码与小节。
        query_string: 原始查询串，支持 ``force``/``page``/``page_size``/``kind``。
        service: 可注入的聚合服务（测试用）；缺省用模块级 ``STOCK_RESEARCH_SERVICE``。

    Returns:
        对应小节的响应字典（含 ``success`` 与各数据源的降级标记）。

    Raises:
        ValueError: 路径无效、代码非法或分页参数不是整数——属于调用方错误，
            由 handler 映射成 400；上游不可用则由 handler 映射成 502。
    """
    route = parse_research_route(path)
    if route is None:
        raise ValueError("研究数据接口路径无效")
    code, section = route
    validate_stock_code(code)
    query = urllib.parse.parse_qs(query_string or "")
    force = (query.get("force") or ["0"])[0] == "1"
    research_service = service or STOCK_RESEARCH_SERVICE
    if section == "overview":
        return research_service.get_overview(code, force=force)
    if section == "capital":
        return research_service.get_capital(code, force=force)
    try:
        page = int((query.get("page") or ["1"])[0])
        page_size = int((query.get("page_size") or ["10"])[0])
    except ValueError as exc:
        raise ValueError("page 和 page_size 必须是整数") from exc
    kind = (query.get("kind") or ["all"])[0]
    return research_service.get_events(
        code,
        kind=kind,
        page=page,
        page_size=page_size,
        force=force,
    )


def json_response(handler: SimpleHTTPRequestHandler, payload: Dict[str, Any], status: int = 200) -> None:
    """统一的 JSON 响应出口。

    固定 ``no-store``（行情与复盘数据不允许浏览器缓存）、UTF-8 与 ``Content-Length``；
    ``ensure_ascii=False`` 保证中文可读，便于直接排查抓包结果。

    Args:
        handler: 当前请求的处理器，用于写状态行与正文。
        payload: 待序列化对象。
        status: HTTP 状态码，默认 200。
    """
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def read_uploaded_image(handler: SimpleHTTPRequestHandler) -> Dict[str, Any]:
    """解析 ``multipart/form-data`` 截图上传。

    Args:
        handler: 处理器，提供 ``rfile`` 与请求头。

    Returns:
        ``{"image_bytes", "mime_type", "trade_date"}``；未带日期时取当天。

    Raises:
        ValueError: 不是 multipart 请求、缺少 ``file`` 字段或解析失败；
            错误文案会直接回给前端，因此不拼接上游响应正文。
    """
    content_type = handler.headers.get("Content-Type", "")
    if not content_type.startswith("multipart/form-data"):
        raise ValueError("请使用 multipart/form-data 上传截图")
    try:
        # cgi 只在截图上传时需要，延迟导入让缺少该模块的环境仍能启动并返回可读错误。
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
    """静态页面与 ``/api/**`` 的请求处理器（仅监听本机回环，无鉴权）。

    路由表：

    - ``GET /api/health``：健康检查，``success=true`` + ``service=python-a``。
    - ``GET /api/stock?code=&force=``：单只行情（带缓存）。
    - ``GET|POST|DELETE /api/watchlist``：自选股列表/新增/删除。
    - ``GET /api/stocks/{code}/research/{overview|capital|events}``：研究数据聚合。
    - ``GET|POST /api/trading/**``：台账、资金流、账户快照、交易、截图解析草稿。
    - ``POST /api/obsidian/**``：复盘写入 Obsidian。
    - ``POST /api/ai/dimension-analysis``：AI 维度分析。
    - 其余路径交给 ``SimpleHTTPRequestHandler`` 直接提供静态文件。

    错误映射：调用方参数问题返回 400，上游数据源问题返回 502，未匹配的 ``/api/**``
    POST 返回 404；响应体统一带 ``ok``/``success`` 与 ``error``/``message``。
    """
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """把静态文件根固定到 ``python-a`` 目录，而不是进程当前目录。

        Args:
            *args: 透传给 ``SimpleHTTPRequestHandler``（socket、客户端地址、server）。
            **kwargs: 其余透传参数；``directory`` 已被本方法覆盖。
        """
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self) -> None:
        """给静态资源补禁缓存头。

        ``/api/**`` 由 ``json_response`` 自行声明 ``no-store``，这里只处理页面与 js/css：
        行情刷新频繁，浏览器缓存旧 ``app.js`` 会让改动看起来没生效。
        """
        parsed = urllib.parse.urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        super().end_headers()

    def do_GET(self) -> None:
        """处理所有只读接口与静态资源。

        路由顺序按特异度排列：先判带正则的研究接口，再是健康检查、行情与交易只读接口，
        最后落到 ``super().do_GET()`` 提供静态文件。

        Returns:
            ``None``；响应直接写入 ``self.wfile``。每个分支都自带异常映射，
            保证单次请求出错不会让服务线程抛出堆栈。
        """
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith("/api/stocks/") and "/research/" in parsed.path:
            try:
                json_response(self, get_research_response(parsed.path, parsed.query))
            except ValueError as exc:
                json_response(self, {"success": False, "message": str(exc)}, status=400)
            except Exception as exc:
                json_response(self, {"success": False, "message": str(exc)}, status=502)
            return
        if parsed.path == "/api/health":
            json_response(
                self,
                {
                    "success": True,
                    "service": "python-a",
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
        # 其余路径交给静态文件服务（index.html / app.js / styles.css）。
        return super().do_GET()

    def do_POST(self) -> None:
        """处理写入类接口：截图解析、Obsidian 写入、AI 分析与台账增改。

        截图接口走 multipart，其余接口统一按 ``Content-Length`` 读取 JSON 正文；
        未匹配的路径返回 404，任何异常都收敛成 400 + 可读原因。

        Returns:
            ``None``；响应直接写入 ``self.wfile``。
        """
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
            # 校验、存储与模型异常统一收敛成 400 + 可读原因，前端据此提示而不是白屏。
            json_response(self, {"ok": False, "success": False, "error": str(exc), "message": str(exc)}, status=400)

    def do_DELETE(self) -> None:
        """删除自选股（当前唯一的 DELETE 接口）。

        只接受 ``/api/watchlist?code=``；其它路径一律 404，避免误删。
        """
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
        """把访问日志压成单行并加时间前缀；stdout 不可用时静默忽略。

        Windows 下控制台被关闭或重定向时 ``print`` 会抛 ``OSError``，这里吞掉，
        避免日志问题影响请求处理。
        """
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {format % args}")
        except OSError:
            pass


def main() -> None:
    """启动入口：准备 vault 目录后用 ``ThreadingHTTPServer`` 阻塞监听。

    只绑定 ``127.0.0.1``：这是个人本机研究台，不对外网暴露；需要统一域名时由上层
    Nginx/Spring 反向代理转发。端口取 ``PORT``，默认 5174。
    """
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
