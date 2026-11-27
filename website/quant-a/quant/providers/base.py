"""行情数据提供方（Provider）的行结构与协议定义。

`DataProvider` 是唯一的数据入口契约：交易日历、股票基础信息、日行情、估值、财务、
指数成分。所有日期都是 `YYYY-MM-DD` 字符串，区间为**闭区间**；价格单位为人民币元，
`turnover_rate` 为百分数（`1.2` 表示 1.2%）。

防未来函数的关键字段是 `available_date`：它表示这条数据在实盘上最早可被看到的交易日
（通常是次一开市日）。下游的选股、因子与回测查询都会附加 `available_date <= 决策日`
条件，保证不会用当天收盘后才公布的行情或财报去交易。

单位陷阱：`volume`（成交量）与 `amount`（成交额）沿用各数据源原始单位，AkShare 为
"手"与"元"，Tushare 为"手"与"千元"，MockProvider 为自造数值，本层不做归一化。
用 `universe.filters.min_avg_amount_20d` 这类金额阈值筛选之前必须先确认 Provider 单位。
"""

from dataclasses import dataclass
from typing import List, Optional, Protocol


@dataclass(frozen=True)
class TradeCalendarRow:
    """一个开市日的日历行。

    字段：
        trade_date: 交易日，`YYYY-MM-DD`。
        is_open: 是否开市；Provider 只返回开市日，因此当前恒为 `True`。
        prev_trade_date: 上一个开市日，区间首日可能为空。
        next_trade_date: 下一个开市日，区间末日可能为空。
        is_month_end: 是否为该月最后一个开市日，供按月调仓使用。
    """

    trade_date: str
    is_open: bool
    prev_trade_date: Optional[str]
    next_trade_date: Optional[str]
    is_month_end: bool


@dataclass(frozen=True)
class StockBasicRow:
    """股票基础信息（静态、低频变化）。

    字段：
        code: 6 位 A 股代码，不带交易所后缀。
        name: 证券简称，用于 `is_st` 判断。
        exchange: `SH`/`SZ`/`BJ`。
        list_date: 上市日期，选股用上市天数过滤次新股。
        delist_date: 退市日期，在市股票为空。
        status: `listed`/`paused`/`delisted`，选股 SQL 只取 `listed`。
        industry: 行业分类，缺失时数据源给 `未分类`。
        is_st: 是否 ST/*ST，默认过滤。
    """

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
    """一个股票一个交易日的行情。

    价格单位为元，`volume`/`amount` 单位随 Provider 而变（见模块说明）。
    `available_date` 必须是该行情真正可见的日期（通常是次一开市日）；回测与因子
    查询都用它挡住未来数据，填成 `trade_date` 会造成前视偏差。
    """

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
    """一个股票一个交易日的估值指标。

    估值字段多为倍数（`pe_ttm`、`pb`、`ps_ttm`、`pcf_ttm`），`dividend_yield` 是小数
    （`0.02` 表示 2%），市值为元。`available_date` 同样用于防前视；中性占位数据的
    `data_version` 会带 `derived-neutral` 标记，避免被误当成真实估值。
    """

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
    """一份财报快照。

    `report_period` 是报告期（如 `2023-12-31`），`announce_date` 是公告日，
    `available_date` 是公告后可用的交易日。用 `report_period` 选最新财报会造成
    前视偏差，下游查询按 `available_date` 过滤。金额单位为元，比率字段
    （`roe`、`roa`、`gross_margin`、`net_margin`、`debt_ratio`）是 0~1 小数。
    """

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
    """指数成分股的生效区间。

    `effective_date`（含）到 `expire_date`（不含，空表示当前仍有效）之间该股票属于
    `index_code`。选股按决策日查询这个区间，避免用"今天的成分股"回测历史（幸存者偏差）。
    """

    index_code: str
    code: str
    effective_date: str
    expire_date: Optional[str]
    data_version: str


class DataProvider(Protocol):
    """数据提供方协议，所有日期区间均为闭区间。

    实现方需自带超时与降级：单个外部接口失败不得让整条流水线不可用。`MockProvider`、
    `AkShareProvider`、`TushareProvider` 都实现该协议，但部分方法在特定 Provider 下
    只返回中性占位数据或直接抛 `NotImplementedError`，调用方需按能力判断。
    """

    def get_trade_calendar(self, start_date: str, end_date: str) -> List[TradeCalendarRow]:
        """返回闭区间内的开市日（只含开市日，按日期升序）。"""
        raise NotImplementedError

    def get_stock_basic(self) -> List[StockBasicRow]:
        """返回全市场股票基础信息；退市与停牌标记由各 Provider 自行映射。"""
        raise NotImplementedError

    def get_daily_bars(self, start_date: str, end_date: str, codes: Optional[List[str]] = None) -> List[DailyBarRow]:
        """返回闭区间内的日行情；`codes` 为空表示全市场。"""
        raise NotImplementedError

    def get_valuation(self, start_date: str, end_date: str, codes: Optional[List[str]] = None) -> List[ValuationRow]:
        """返回闭区间内的估值指标；`codes` 为空表示全市场。"""
        raise NotImplementedError

    def get_financials(self) -> List[FinancialRow]:
        """返回可见的财报快照；是否支持取决于 Provider 的权限与实现程度。"""
        raise NotImplementedError

    def get_index_members(self, index_codes: List[str], trade_date: str) -> List[IndexMemberRow]:
        """返回 `trade_date` 当日的指数成分；特殊代码 `ALL`/`FULL_MARKET` 表示全市场。"""
        raise NotImplementedError
