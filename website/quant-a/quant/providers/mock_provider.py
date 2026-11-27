"""确定性假数据 Provider `MockProvider`。

供单元测试与离线演示使用：6 只虚构股票、工作日日历、按序号线性递增的价格序列，
不访问任何网络。数据版本固定为 `mock-2024-q1`，所有行的 `data_version` 都带该标记，
报告里也据此提示"mock 数据只验证流程、不代表真实市场"。

刻意保留的缺陷（不要用它评估策略收益）：价格单调上升、没有停牌与涨跌停约束、
指数成分只有 2024-01-01 起的一段且无失效日（无成分股历史，无法消除幸存者偏差）、
估值是写死的倍数、财报只有一期。它只保证字段齐全与接口形状稳定。
"""

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
    """内存中的确定性行情源，行为完全可复现。"""

    name = "mock"
    data_version = "mock-2024-q1"
    closed_dates = {"2024-01-01"}

    codes = [
        ("600001", "浦江制造", "SH", "2010-01-01", "工业", False),
        ("600002", "海岳能源", "SH", "2012-05-10", "能源", False),
        ("600003", "星河科技", "SH", "2016-03-18", "科技", False),
        ("000001", "南方银行", "SZ", "1991-04-03", "金融", False),
        ("000002", "长风地产", "SZ", "2001-09-21", "地产", False),
        ("000003", "华康医药", "SZ", "2018-07-11", "医药", False),
    ]

    def get_trade_calendar(self, start_date: str, end_date: str) -> List[TradeCalendarRow]:
        """按"工作日减去 `closed_dates`"生成日历。

        Args:
            start_date: 区间起（含），ISO 日期。
            end_date: 区间止（含），ISO 日期。

        Returns:
            升序开市日行；`next_trade_date` 只在本次区间内有效，区间末日为空，
            `is_month_end` 按"下一开市日已跨月"判断。不识别法定节假日。
        """
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        days = []
        current = start
        while current <= end:
            if current.weekday() < 5 and current.isoformat() not in self.closed_dates:
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
        """返回 6 只虚构股票的基础信息（全部在市、非 ST、有行业）。"""
        return [
            StockBasicRow(code, name, exchange, list_date, None, "listed", industry, is_st)
            for code, name, exchange, list_date, industry, is_st in self.codes
        ]

    def get_index_members(self, index_codes: List[str], trade_date: str) -> List[IndexMemberRow]:
        """把 6 只虚构股票都当作每个指数的成分股。

        成分区间固定从 `2024-01-01` 开始且无失效日，只有一段历史，因此无法复现
        成分股调整，回测存在幸存者偏差；这也是 mock 数据只能验证流程的原因之一。
        """
        rows = []
        for index_code in index_codes:
            for code, *_ in self.codes:
                rows.append(IndexMemberRow(index_code, code, "2024-01-01", None, self.data_version))
        return rows

    def get_daily_bars(self, start_date: str, end_date: str, codes: List[str] = None) -> List[DailyBarRow]:
        """生成一段确定性的日行情。

        价格按"股票序号定基价、交易日序号定涨幅"线性递增，`amount = volume * close`，
        涨跌停统一按前收 ±10% 计算（不区分主板/创业板/北交所，也无停牌），
        `adj_factor` 恒为 1.0（不复权）。`available_date` 取次一开市日，
        保证下游按可用日过滤时不会用到当天收盘后才知道的价格。

        Args:
            start_date: 区间起（含），ISO 日期。
            end_date: 区间止（含），ISO 日期。
            codes: 可选代码过滤；为空时返回全部 6 只。

        Returns:
            按股票、交易日展开的行情行；同一输入永远得到同一输出。
        """
        calendar = self.get_trade_calendar(start_date, end_date)
        code_filter = set(codes or [])
        rows = []
        for code_index, (code, *_rest) in enumerate(self.codes):
            if code_filter and code not in code_filter:
                continue
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
                    volume=5000000 + code_index * 500000,
                    amount=(5000000 + code_index * 500000) * close,
                    turnover_rate=1.5 + code_index * 0.2,
                    adj_factor=1.0,
                    limit_up=round(pre_close * 1.1, 2),
                    limit_down=round(pre_close * 0.9, 2),
                    suspend_flag=False,
                    available_date=self._available_date(cal),
                    data_version=self.data_version,
                ))
        return rows

    def get_valuation(self, start_date: str, end_date: str, codes: List[str] = None) -> List[ValuationRow]:
        """生成与行情日期对齐的估值行。

        各倍数按股票序号递增，市值为元；`available_date` 与行情一致（次一开市日）。
        数值是写死的样例，不能用于判断估值高低。
        """
        calendar = self.get_trade_calendar(start_date, end_date)
        code_filter = set(codes or [])
        rows = []
        for code_index, (code, *_rest) in enumerate(self.codes):
            if code_filter and code not in code_filter:
                continue
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
                    available_date=self._available_date(cal),
                    data_version=self.data_version,
                ))
        return rows

    def derive_valuation_from_daily_bars(self, daily_bars: List[DailyBarRow]) -> List[ValuationRow]:
        """用已抓到的行情日期反推一批估值行。

        这是 `QuantPipeline` 批量同步行情时优先调用的能力：只遍历一次行情就能同时
        写入 `daily_bar` 与 `valuation`。未知代码按序号 0 处理（不会报错）。

        Args:
            daily_bars: 已获取的行情行，估值行的日期与 `available_date` 均从它复制。

        Returns:
            与输入等长的估值行列表。
        """
        rows = []
        code_indexes = {code: index for index, (code, *_rest) in enumerate(self.codes)}
        for bar in daily_bars:
            code_index = code_indexes.get(bar.code, 0)
            rows.append(ValuationRow(
                trade_date=bar.trade_date,
                code=bar.code,
                pe_ttm=12.0 + code_index * 2,
                pb=1.1 + code_index * 0.2,
                ps_ttm=1.8 + code_index * 0.3,
                pcf_ttm=9.0 + code_index,
                dividend_yield=0.01 + code_index * 0.002,
                total_market_value=20000000000 + code_index * 3000000000,
                float_market_value=15000000000 + code_index * 2500000000,
                available_date=bar.available_date,
                data_version=self.data_version,
            ))
        return rows

    def get_financials(self) -> List[FinancialRow]:
        """返回 6 只股票各一期 2023 年报。

        公告日 2024-01-15、可用日 2024-01-16，正好落在默认同步区间内，便于测试
        "财报在可见日之前不可用"；金额单位为元，比率字段为 0~1 小数。
        """
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

    def _available_date(self, calendar_row: TradeCalendarRow) -> str:
        """计算一条行情最早可见的日期。

        优先用日历里已有的下一个开市日；区间最后一天没有下一日时，向后逐日找第一个
        "非周末且不在 `closed_dates`"的日期，避免返回空字符串让下游过滤失效。

        Args:
            calendar_row: 该行情对应的日历行。

        Returns:
            次一开市日的 ISO 日期字符串。
        """
        if calendar_row.next_trade_date:
            return calendar_row.next_trade_date

        current = date.fromisoformat(calendar_row.trade_date) + timedelta(days=1)
        while current.weekday() >= 5 or current.isoformat() in self.closed_dates:
            current += timedelta(days=1)
        return current.isoformat()
