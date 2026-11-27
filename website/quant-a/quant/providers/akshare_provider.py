"""AkShare 行情 Provider `AkShareProvider`。

日行情来自 AkShare 的 `stock_zh_a_hist`（前复权）；单只股票抓取失败时按
"东方财富 K 线 → 新浪日线"的顺序降级，三条路都失败只把代码记进 `self.errors`，
不向上抛异常，避免一只股票拖垮整轮同步。估值与财务是显式标记为 `derived-neutral`
的中性占位数据，防止把编造的数字误当成真实估值或真实财报。

数据版本：实例化时把当天日期写进 `data_version`；每条行情行的 `data_version` 记录
实际来源与交易日（`akshare-YYYYMMDD`、`eastmoney-YYYYMMDD`、`sina-YYYYMMDD`）。

超时与近似：东方财富、新浪的 HTTP 请求都带 `timeout_seconds`，但 AkShare 的
`stock_zh_a_hist` 没有超时参数，其内部请求可能长时间阻塞。交易日历只按工作日近似
（不含法定节假日），涨跌停按前收 ±10% 估算（不区分主板/创业板/北交所与 ST），
可转债、停牌与复权细节也未覆盖；这些近似必须在报告偏差披露中说明。
"""

import math
from datetime import date, datetime, timedelta
from typing import List, Optional

import requests

from quant.providers.base import (
    DailyBarRow,
    FinancialRow,
    IndexMemberRow,
    StockBasicRow,
    TradeCalendarRow,
    ValuationRow,
)


AKSHARE_INSTALL_MESSAGE = "AkShare is not installed. Run: python -m pip install -r requirements.txt"


class AkShareProvider:
    """AkShare 行情接入。

    第一阶段只做快速接入：日行情来自 AkShare，估值和财务使用明确标记的中性占位数据，
    避免把派生数据误认为真实估值或真实财报。所有外部异常都在方法内部转成
    `self.errors` / `self.warnings`，不向调用方抛出。
    """

    name = "akshare"

    def __init__(self, timeout_seconds: int = 15):
        """记录超时并生成当天版本号。

        Args:
            timeout_seconds: 东方财富/新浪兜底请求的超时秒数，默认 15；AkShare 自身
                调用不受该参数约束。
        """
        today = date.today().strftime("%Y%m%d")
        self.timeout_seconds = timeout_seconds
        self.data_version = "akshare-%s" % today
        self.errors = []
        self.warnings = []

    def get_trade_calendar(self, start_date: str, end_date: str) -> List[TradeCalendarRow]:
        """按工作日近似交易日历（不识别法定节假日）。

        Args:
            start_date: 区间起（含），ISO 日期。
            end_date: 区间止（含），ISO 日期。

        Returns:
            周一至周五的日历行；`next_trade_date` 只在本次区间内有效，
            `is_month_end` 按"下一开市日已跨月"判断。春节等长假会被误当成交易日，
            同步到这些日期时行情为空，不会产生错误的成交价。
        """
        # 第一版用工作日近似交易日，法定节假日休市可能不完整，后续替换为交易所日历。
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
        """拉取全市场股票代码与名称。

        只取代码和名称两个字段；`list_date` 统一填 `1990-01-01`、`industry` 填
        `未分类`，所以依赖上市天数的过滤会放行全部股票。`is_st` 用名称是否包含
        `ST` 判断。缺少代码或名称的行直接跳过。

        Returns:
            股票基础信息行；交易所由代码前缀推断（见 `_infer_exchange`）。

        Raises:
            RuntimeError: 未安装 AkShare 时由 `_akshare` 抛出。
        """
        ak = self._akshare()
        df = ak.stock_info_a_code_name()
        rows = []
        for item in df.to_dict("records"):
            code = self._clean_code(self._pick(item, ["code", "代码", "证券代码"]))
            name = str(self._pick(item, ["name", "名称", "证券简称"]) or "").strip()
            if not code or not name:
                continue
            rows.append(StockBasicRow(
                code=code,
                name=name,
                exchange=self._infer_exchange(code),
                list_date="1990-01-01",
                delist_date=None,
                status="listed",
                industry="未分类",
                is_st="ST" in name.upper(),
            ))
        return rows

    def get_daily_bars(self, start_date: str, end_date: str, codes: Optional[List[str]] = None) -> List[DailyBarRow]:
        """逐只股票拉取前复权日行情，失败时走两级兜底。

        处理顺序：AkShare `stock_zh_a_hist` → 东方财富 K 线 → 新浪日线；前一级失败
        时记下异常但继续尝试，只有三级都失败才把 `{"code", "message"}` 追加到
        `self.errors` 并跳过该股票。方法开头会清空 `self.errors`，`self.warnings`
        则是累积的，便于一次同步结束后统一展示。

        `pre_close` 由 `昨收` 字段或 `涨跌幅` 反推；涨跌停按前收 ±10% 估算；
        `available_date` 取次一工作日，保证下游不会用到当天收盘后才可知的价格。
        全市场逐只请求耗时较长，`codes` 过滤应尽量传具体代码。

        Args:
            start_date: 区间起（含），ISO 日期。
            end_date: 区间止（含），ISO 日期。
            codes: 可选代码过滤；为空时遍历全市场。

        Returns:
            成功抓到的行情行；区间外的行会被丢弃，失败股票不出现在结果中。

        Raises:
            RuntimeError: 未安装 AkShare 时由 `_akshare` 抛出（在逐股循环之前）。
        """
        ak = self._akshare()
        self.errors = []
        calendar_by_date = {row.trade_date: row for row in self.get_trade_calendar(start_date, end_date)}
        code_filter = set(codes or [])
        rows = []
        for stock in self.get_stock_basic():
            if code_filter and stock.code not in code_filter:
                continue
            try:
                df = ak.stock_zh_a_hist(
                    symbol=stock.code,
                    period="daily",
                    start_date=self._compact_date(start_date),
                    end_date=self._compact_date(end_date),
                    adjust="qfq",
                )
            except Exception as exc:
                try:
                    fallback_rows = self._eastmoney_daily_bars(stock, start_date, end_date, calendar_by_date)
                except Exception:
                    fallback_rows = []
                if not fallback_rows:
                    try:
                        fallback_rows = self._sina_daily_bars(stock, start_date, end_date, calendar_by_date)
                    except Exception:
                        fallback_rows = []
                if fallback_rows:
                    rows.extend(fallback_rows)
                    continue
                self.errors.append({"code": stock.code, "message": str(exc)})
                continue

            for item in df.to_dict("records"):
                trade_date = self._normalize_date(self._pick(item, ["日期", "date", "trade_date"]))
                if not trade_date or trade_date < start_date or trade_date > end_date:
                    continue
                pre_close = self._pre_close(item)
                calendar_row = calendar_by_date.get(trade_date)
                rows.append(DailyBarRow(
                    trade_date=trade_date,
                    code=stock.code,
                    open=self._float(item, ["开盘", "open"]),
                    high=self._float(item, ["最高", "high"]),
                    low=self._float(item, ["最低", "low"]),
                    close=self._float(item, ["收盘", "close"]),
                    pre_close=pre_close,
                    volume=self._float(item, ["成交量", "volume"]),
                    amount=self._float(item, ["成交额", "amount"]),
                    turnover_rate=self._float(item, ["换手率", "turnover_rate"]),
                    adj_factor=1.0,
                    limit_up=round(pre_close * 1.1, 2),
                    limit_down=round(pre_close * 0.9, 2),
                    suspend_flag=False,
                    available_date=self._available_date(trade_date, calendar_row),
                    data_version="akshare-%s" % self._compact_date(trade_date),
                ))
        return rows

    def _eastmoney_daily_bars(
        self,
        stock: StockBasicRow,
        start_date: str,
        end_date: str,
        calendar_by_date: dict,
    ) -> List[DailyBarRow]:
        """用东方财富 K 线接口兜底单只股票的日行情。

        请求 `klt=101`（日线）、`fqt=1`（前复权）；`klines` 是逗号分隔字符串，
        依次为 日期、开、收、高、低、成交量（手）、成交额（元）、振幅、涨跌幅（%）、
        涨跌额、换手率（%），少于 11 段的行直接跳过。`pre_close` 用涨跌幅反推，
        `pct_change <= -100` 时无法反推，退回当日收盘价。`secid` 的市场号只区分
        沪（1）深（0），北交所股票会取不到数据。

        Args:
            stock: 目标股票基础信息（只用到 `code`）。
            start_date: 区间起（含），ISO 日期。
            end_date: 区间止（含），ISO 日期。
            calendar_by_date: 交易日 → 日历行的映射，用于取 `next_trade_date`。

        Returns:
            行情行列表；接口返回空数据时是空列表。

        Raises:
            requests.RequestException: 连接失败、超时或非 2xx（由
                `raise_for_status` 抛出），由 `get_daily_bars` 捕获后继续尝试新浪。
            ValueError: 响应体不是合法 JSON。
        """
        response = requests.get(
            "https://push2his.eastmoney.com/api/qt/stock/kline/get",
            params={
                "secid": "%s.%s" % (self._eastmoney_market_id(stock.code), stock.code),
                "fields1": "f1,f2,f3,f4,f5,f6",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
                "klt": "101",
                "fqt": "1",
                "beg": self._compact_date(start_date),
                "end": self._compact_date(end_date),
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        klines = ((response.json() or {}).get("data") or {}).get("klines") or []
        rows = []
        for line in klines:
            parts = str(line).split(",")
            if len(parts) < 11:
                continue
            trade_date = self._normalize_date(parts[0])
            if not trade_date or trade_date < start_date or trade_date > end_date:
                continue
            close = self._to_float(parts[2])
            pct_change = self._to_float(parts[8])
            pre_close = close if pct_change <= -100 else round(close / (1 + pct_change / 100), 2)
            calendar_row = calendar_by_date.get(trade_date)
            rows.append(DailyBarRow(
                trade_date=trade_date,
                code=stock.code,
                open=self._to_float(parts[1]),
                high=self._to_float(parts[3]),
                low=self._to_float(parts[4]),
                close=close,
                pre_close=pre_close,
                volume=self._to_float(parts[5]),
                amount=self._to_float(parts[6]),
                turnover_rate=self._to_float(parts[10]),
                adj_factor=1.0,
                limit_up=round(pre_close * 1.1, 2),
                limit_down=round(pre_close * 0.9, 2),
                suspend_flag=False,
                available_date=self._available_date(trade_date, calendar_row),
                data_version="eastmoney-%s" % self._compact_date(trade_date),
            ))
        return rows

    def _sina_daily_bars(
        self,
        stock: StockBasicRow,
        start_date: str,
        end_date: str,
        calendar_by_date: dict,
    ) -> List[DailyBarRow]:
        """用新浪日线接口兜底单只股票的行情。

        `scale=240` 表示日线、`datalen=260` 限制最多返回约一年数据，因此长区间回测
        只能拿到最近一段。`pre_close` 取序列中的前一根收盘价（第一根退化为当日收盘），
        该计算在区间过滤之前完成，所以起止边界上的前收仍然正确；`amount` 没有原始
        字段，用 `volume * close` 估算，并据此把 `turnover_rate` 置 0。

        Args:
            stock: 目标股票基础信息（只用到 `code`）。
            start_date: 区间起（含），ISO 日期。
            end_date: 区间止（含），ISO 日期。
            calendar_by_date: 交易日 → 日历行的映射。

        Returns:
            区间内的行情行；接口返回空数组时是空列表。

        Raises:
            requests.RequestException: 连接失败、超时或非 2xx。
            ValueError: 响应体不是合法 JSON。
        """
        response = requests.get(
            "https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketData.getKLineData",
            params={
                "symbol": "%s%s" % (self._sina_market_prefix(stock.code), stock.code),
                "scale": "240",
                "ma": "no",
                "datalen": "260",
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        items = response.json() or []
        rows = []
        previous_close = None
        for item in items:
            trade_date = self._normalize_date(item.get("day"))
            if not trade_date:
                continue
            close = self._to_float(item.get("close"))
            pre_close = previous_close if previous_close is not None else close
            previous_close = close
            if trade_date < start_date or trade_date > end_date:
                continue
            calendar_row = calendar_by_date.get(trade_date)
            volume = self._to_float(item.get("volume"))
            rows.append(DailyBarRow(
                trade_date=trade_date,
                code=stock.code,
                open=self._to_float(item.get("open")),
                high=self._to_float(item.get("high")),
                low=self._to_float(item.get("low")),
                close=close,
                pre_close=pre_close,
                volume=volume,
                amount=round(volume * close, 4),
                turnover_rate=0.0,
                adj_factor=1.0,
                limit_up=round(pre_close * 1.1, 2),
                limit_down=round(pre_close * 0.9, 2),
                suspend_flag=False,
                available_date=self._available_date(trade_date, calendar_row),
                data_version="sina-%s" % self._compact_date(trade_date),
            ))
        return rows

    def _sina_market_prefix(self, code: str) -> str:
        """按代码前缀给出新浪的交易所前缀：`6`/`9` 开头为 `sh`，其余为 `sz`。

        北交所（`4`/`8` 开头）也会落到 `sz`，新浪取不到数据，由外层兜底失败处理。
        """
        if code.startswith(("6", "9")):
            return "sh"
        return "sz"

    def _eastmoney_market_id(self, code: str) -> str:
        """按代码前缀给出东方财富的市场号：沪市为 `1`，深市为 `0`。"""
        if code.startswith(("6", "9")):
            return "1"
        return "0"

    def get_valuation(self, start_date: str, end_date: str, codes: Optional[List[str]] = None) -> List[ValuationRow]:
        """先用日行情定位有数据的股票与日期，再生成中性估值占位行。

        估值本身没有真实数据源，因此覆盖范围严格受限于取到的行情：抓不到行情的股票
        也就没有估值行。

        Args:
            start_date: 区间起（含），ISO 日期。
            end_date: 区间止（含），ISO 日期。
            codes: 可选代码过滤，透传给 `get_daily_bars`。

        Returns:
            与行情行等长的估值行，`data_version` 带 `derived-neutral` 标记。
        """
        return self.derive_valuation_from_daily_bars(self.get_daily_bars(start_date, end_date, codes=codes))

    def derive_valuation_from_daily_bars(self, daily_bars: List[DailyBarRow]) -> List[ValuationRow]:
        """按行情行生成中性估值占位数据。

        固定 `pe_ttm=15`、`pb=1.5`、`ps_ttm=2.0`、`pcf_ttm=10.0`、
        `dividend_yield=0.02`（小数），市值填 0；`data_version` 以
        `akshare-derived-neutral-` 前缀显式标注，便于报告与排查时识别。
        这些数字不具备任何估值含义，因子层把它们当作同一横截面上的常数，
        等价于该维度不参与排序。

        Args:
            daily_bars: 已获取的行情行，日期与 `available_date` 由它复制。

        Returns:
            与输入等长的估值行列表。
        """
        rows = []
        for bar in daily_bars:
            rows.append(ValuationRow(
                trade_date=bar.trade_date,
                code=bar.code,
                pe_ttm=15.0,
                pb=1.5,
                ps_ttm=2.0,
                pcf_ttm=10.0,
                dividend_yield=0.02,
                total_market_value=0.0,
                float_market_value=0.0,
                available_date=bar.available_date,
                data_version="akshare-derived-neutral-%s" % self._compact_date(bar.trade_date),
            ))
        return rows

    def get_financials(self) -> List[FinancialRow]:
        """为每只股票生成一条中性占位财报。

        报告期、公告日、可用日都写成 `1990-01-01`，使这条记录在任何决策日都"已可见"；
        `data_version` 为 `akshare-derived-neutral-financial`。财务因子因此对所有股票
        取同一组常数，等价于不提供质量维度差异——接入真实财报前不应解读质量评分。

        Returns:
            与在市股票数量相同的财报行；未安装 AkShare 时抛 `RuntimeError`。
        """
        rows = []
        for stock in self.get_stock_basic():
            rows.append(FinancialRow(
                code=stock.code,
                report_period="1990-01-01",
                announce_date="1990-01-01",
                available_date="1990-01-01",
                revenue=1000000000.0,
                net_profit=100000000.0,
                deducted_net_profit=90000000.0,
                operating_cash_flow=120000000.0,
                roe=0.08,
                roa=0.04,
                gross_margin=0.25,
                net_margin=0.10,
                debt_ratio=0.50,
                data_version="akshare-derived-neutral-financial",
            ))
        return rows

    def get_index_members(self, index_codes: List[str], trade_date: str) -> List[IndexMemberRow]:
        """用全市场股票近似任意指数的成分股。

        除 `ALL`/`FULL_MARKET` 外，每个指数都会往 `self.warnings` 写一条"暂时用全市场
        近似"的提示；成分区间从 `trade_date` 开始且无失效日，没有历史调整记录，
        因此按指数回测时实际得到的是全市场池，且存在幸存者偏差。警告会持续累积，
        调用方应在同步结束后统一展示。

        Args:
            index_codes: 指数代码列表；`ALL`/`FULL_MARKET` 表示全市场，不产生警告。
            trade_date: 成分生效日，直接写入 `effective_date`。

        Returns:
            指数代码 × 全部股票的成分行。

        Raises:
            RuntimeError: 未安装 AkShare 时由 `get_stock_basic` 抛出。
        """
        stocks = self.get_stock_basic()
        rows = []
        for index_code in index_codes:
            normalized_index = index_code.upper()
            if normalized_index not in {"ALL", "FULL_MARKET"}:
                self.warnings.append(
                    "%s index members are temporarily approximated with full-market members." % index_code
                )
            for stock in stocks:
                rows.append(IndexMemberRow(
                    index_code=index_code,
                    code=stock.code,
                    effective_date=trade_date,
                    expire_date=None,
                    data_version=self.data_version,
                ))
        return rows

    def _akshare(self):
        """延迟导入 AkShare 模块。

        把依赖检查推迟到真正调用数据接口时，`create_provider` 才能在未安装 AkShare 的
        环境里构造本对象（测试会把它替换成假模块）。

        Returns:
            `akshare` 模块对象。

        Raises:
            RuntimeError: 未安装 AkShare，附带 `pip install -r requirements.txt` 提示。
        """
        try:
            import akshare as ak
        except ImportError as exc:
            raise RuntimeError(AKSHARE_INSTALL_MESSAGE) from exc
        if ak is None:
            raise RuntimeError(AKSHARE_INSTALL_MESSAGE)
        return ak

    def _available_date(self, trade_date: str, calendar_row: Optional[TradeCalendarRow]) -> str:
        """计算一条行情最早可见的日期（次一开市日）。

        优先用日历行的 `next_trade_date`；区间末日没有下一日时向后找第一个工作日。
        只跳过周末、不识别法定节假日，结果可能比真实可用日更晚，但不会更早，
        因此不会引入前视偏差。

        Args:
            trade_date: 行情所属交易日。
            calendar_row: 对应的日历行，可能为空（例如日历里漏了这一天）。

        Returns:
            次一开市日的 ISO 日期字符串。
        """
        if calendar_row and calendar_row.next_trade_date:
            return calendar_row.next_trade_date

        current = date.fromisoformat(trade_date) + timedelta(days=1)
        while current.weekday() >= 5:
            current += timedelta(days=1)
        return current.isoformat()

    def _pre_close(self, item: dict) -> float:
        """解析昨日收盘价。

        优先取 `昨收`/`pre_close`；缺失时用收盘价与 `涨跌幅` 反推。涨跌幅小于等于
        -100% 时反推会除零或得到负价（除权、数据异常），此时退回当日收盘价，
        保证 `limit_up`/`limit_down` 至少是正数。

        Args:
            item: AkShare 返回的一行记录字典。

        Returns:
            昨收价（元）；字段全缺时返回 0.0。
        """
        pre_close = self._pick(item, ["昨收", "pre_close"])
        if pre_close not in (None, ""):
            return self._to_float(pre_close)
        close = self._float(item, ["收盘", "close"])
        pct_change = self._float(item, ["涨跌幅", "pct_chg", "change_pct"])
        if pct_change <= -100:
            return close
        return round(close / (1 + pct_change / 100), 2)

    def _float(self, item: dict, keys: List[str]) -> float:
        """按候选列名取数并转成 float；列缺失或空值返回 0.0。"""
        return self._to_float(self._pick(item, keys))

    def _to_float(self, value) -> float:
        """把任意值转成 float，`None`、空串与 NaN 统一记 0.0。

        AkShare 的 DataFrame 会把缺失值变成 `NaN`，直接 `float()` 会得到 NaN 并污染
        后续均值/排名计算，因此这里显式拦掉。
        """
        if value is None or value == "":
            return 0.0
        if isinstance(value, float) and math.isnan(value):
            return 0.0
        return float(value)

    def _pick(self, item: dict, keys: List[str]):
        """按顺序返回第一个存在的列值，全部缺失返回 `None`。

        用于兼容 AkShare 不同接口/版本的中英文列名（如 `收盘`、`close`）；
        注意"存在但为 None"也会被当作命中，交由 `_to_float` 兜底。

        Args:
            item: 一行记录字典。
            keys: 候选列名，按优先级排列。

        Returns:
            第一个命中的原始值，或 `None`。
        """
        for key in keys:
            if key in item:
                return item[key]
        return None

    def _compact_date(self, value: str) -> str:
        """去掉短横线，得到 AkShare/东方财富接口需要的 `YYYYMMDD`。"""
        return value.replace("-", "")

    def _normalize_date(self, value) -> Optional[str]:
        """把多种日期表示统一成 ISO `YYYY-MM-DD`。

        支持 `datetime`/`date` 对象、`YYYYMMDD` 数字串与带时间部分的字符串；
        空值返回 `None`。无法识别时退化为截取前 10 个字符，异常格式不会抛错，
        但可能产生不合法的日期串交给下游比较。

        Args:
            value: 原始日期值。

        Returns:
            ISO 日期字符串或 `None`。
        """
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        text = str(value).strip()
        if len(text) == 8 and text.isdigit():
            return "%s-%s-%s" % (text[:4], text[4:6], text[6:])
        return text[:10]

    def _clean_code(self, value) -> str:
        """规整股票代码：去掉 `600001.SH` 这类后缀并左补零到 6 位。

        Args:
            value: 原始代码，可能为空。

        Returns:
            6 位代码字符串；空值返回空串，由调用方跳过该行。
        """
        if value is None:
            return ""
        text = str(value).strip()
        if "." in text:
            text = text.split(".")[0]
        return text.zfill(6)

    def _infer_exchange(self, code: str) -> str:
        """按代码前缀推断交易所：`6`/`9` 为沪市，`8`/`4` 为北交所，其余为深市。

        只是启发式判断，不校验代码是否真实存在；科创板与创业板也分别落在 `SH`/`SZ`。
        """
        if code.startswith(("6", "9")):
            return "SH"
        if code.startswith(("8", "4")):
            return "BJ"
        return "SZ"
