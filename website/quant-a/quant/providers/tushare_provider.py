"""Tushare Pro 行情 Provider `TushareProvider`。

需要 `TUSHARE_TOKEN`（或 `provider.tushare.token_env` 指定的环境变量名）以及对应
接口权限。token 在构造时读取一次，`tushare` 包在首次调用接口时延迟导入，
所以"只配置、不使用"不会触发依赖检查。

能力边界：交易日历、股票基础信息、日行情、估值已映射；财务与指数成分需要额外权限，
直接抛 `NotImplementedError`。若干字段是占位值而非真实数据——`turnover_rate=0`、
`adj_factor=1.0`、涨跌停价为 0、`suspend_flag=False`，`get_daily_bars` 返回未复权
行情且不接受 `codes` 过滤（会拉全市场）。单位沿用 Tushare 原生口径：`amount` 为千元、
市值为万元、`dv_ttm` 为百分数，与 `MockProvider`/`AkShareProvider` 不一致，
混用或套用金额阈值前必须先换算。
"""

import importlib
import os
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from quant.providers.base import (
    DailyBarRow,
    FinancialRow,
    IndexMemberRow,
    StockBasicRow,
    TradeCalendarRow,
    ValuationRow,
)


class TushareProvider:
    """基于 Tushare Pro SDK 的行情实现。"""

    name = "tushare"
    data_version = "tushare-v1"

    def __init__(self, timeout_seconds: int = 15, token_env: str = "TUSHARE_TOKEN"):
        """读取 token 环境变量名并记住超时配置。

        注意：`timeout_seconds` 目前只做保存，Tushare SDK 的 `pro_api`/接口调用没有
        超时入参，因此真实网络请求不受该超时约束；上游卡住时调用线程会一直等待。

        Args:
            timeout_seconds: 期望的超时秒数（当前不生效，保留给后续封装）。
            token_env: 存放 Tushare token 的环境变量名，构造时读取并去空白。
        """
        self.timeout_seconds = timeout_seconds
        self.token_env = token_env
        self.token = os.environ.get(token_env, "").strip()
        self._pro = None

    def get_stock_basic(self) -> List[StockBasicRow]:
        """拉取在市股票（`list_status="L"`）并映射为行对象。

        只请求在市股票，退市股不在结果里，直接用它回测会引入幸存者偏差。
        `is_st` 通过名称包含 `ST` 判断（大小写不敏感），与真实风险警示口径可能有偏差。

        Returns:
            股票基础信息行；代码去掉交易所后缀变 6 位数字，空日期字段保持空串。

        Raises:
            RuntimeError: 未配置 token 或未安装 `tushare` 包（由 `_pro_api` 抛出）。
        """
        rows = self._to_records(self._pro_api().stock_basic(
            exchange="",
            list_status="L",
            fields="ts_code,name,exchange,list_date,delist_date,list_status,industry",
        ))
        return [
            StockBasicRow(
                code=self._stock_code(row.get("ts_code")),
                name=self._text(row.get("name")),
                exchange=self._text(row.get("exchange")),
                list_date=self._format_date(row.get("list_date")),
                delist_date=self._optional_date(row.get("delist_date")),
                status=self._map_status(row.get("list_status")),
                industry=self._text(row.get("industry")),
                is_st="ST" in self._text(row.get("name")).upper(),
            )
            for row in rows
        ]

    def get_trade_calendar(self, start_date: str, end_date: str) -> List[TradeCalendarRow]:
        """拉取交易日历并只保留开市日。

        `exchange=""` 表示请求全部交易所；`is_open` 为 1 的记录按日期升序排列后，
        `next_trade_date` 取自列表中的下一条（区间末日为空），`prev_trade_date` 用
        交易所返回的 `pretrade_date`，因此可能指向上一个区间之外的交易日。

        Args:
            start_date: 区间起（含），ISO 日期。
            end_date: 区间止（含），ISO 日期。

        Returns:
            开市日行列表；`is_month_end` 按"下一个开市日已跨月"判断。

        Raises:
            RuntimeError: 未配置 token 或未安装 `tushare` 包。
        """
        records = self._to_records(self._pro_api().trade_cal(
            exchange="",
            start_date=self._compact_date(start_date),
            end_date=self._compact_date(end_date),
        ))
        open_days = [row for row in records if int(row.get("is_open") or 0) == 1]
        open_days.sort(key=lambda item: self._compact_date(item.get("cal_date")))

        rows = []
        for index, row in enumerate(open_days):
            trade_date = self._format_date(row.get("cal_date"))
            next_trade_date = self._format_date(open_days[index + 1].get("cal_date")) if index + 1 < len(open_days) else None
            rows.append(TradeCalendarRow(
                trade_date=trade_date,
                is_open=True,
                prev_trade_date=self._optional_date(row.get("pretrade_date")),
                next_trade_date=next_trade_date,
                is_month_end=next_trade_date is None or next_trade_date[:7] != trade_date[:7],
            ))
        return rows

    def get_daily_bars(self, start_date: str, end_date: str) -> List[DailyBarRow]:
        """拉取未复权日行情并映射为行对象。

        与协议相比少一个可选的 `codes` 参数：Tushare 的 `daily` 不传 `ts_code` 时返回
        全市场，本实现因此一次性拉取区间内所有股票，数据量大时需要注意内存与耗时。
        `volume` 单位为手、`amount` 为千元，不做换算；`turnover_rate`、`limit_up`、
        `limit_down`、`suspend_flag` 都是占位值（0/0/0/False），不能当作真实约束。
        `available_date` 只跳过周末，不含法定节假日。

        Args:
            start_date: 区间起（含），ISO 日期。
            end_date: 区间止（含），ISO 日期。

        Returns:
            日行情行列表，`data_version` 固定为 `tushare-v1`。

        Raises:
            RuntimeError: 未配置 token 或未安装 `tushare` 包。
        """
        rows = self._to_records(self._pro_api().daily(
            start_date=self._compact_date(start_date),
            end_date=self._compact_date(end_date),
        ))
        return [
            DailyBarRow(
                trade_date=self._format_date(row.get("trade_date")),
                code=self._stock_code(row.get("ts_code")),
                open=self._float(row.get("open")),
                high=self._float(row.get("high")),
                low=self._float(row.get("low")),
                close=self._float(row.get("close")),
                pre_close=self._float(row.get("pre_close")),
                volume=self._float(row.get("vol")),
                amount=self._float(row.get("amount")),
                turnover_rate=0.0,
                adj_factor=1.0,
                limit_up=0.0,
                limit_down=0.0,
                suspend_flag=False,
                available_date=self._next_business_date(row.get("trade_date")),
                data_version=self.data_version,
            )
            for row in rows
        ]

    def get_valuation(self, start_date: str, end_date: str) -> List[ValuationRow]:
        """拉取每日估值指标并映射为行对象。

        与协议相比少一个可选的 `codes` 参数，因此同样是一次拉全市场。单位陷阱：
        `total_mv`/`circ_mv` 是万元、`dv_ttm` 是百分数，都原样写入，未换算成
        `base.py` 声明的元与小数口径；`pcf_ttm` 优先取 `pcf_ttm`，字段缺失时回退
        旧字段 `pcf`。

        Args:
            start_date: 区间起（含），ISO 日期。
            end_date: 区间止（含），ISO 日期。

        Returns:
            估值行列表，`available_date` 为跳过周末的次一日。

        Raises:
            RuntimeError: 未配置 token 或未安装 `tushare` 包。
        """
        rows = self._to_records(self._pro_api().daily_basic(
            start_date=self._compact_date(start_date),
            end_date=self._compact_date(end_date),
        ))
        return [
            ValuationRow(
                trade_date=self._format_date(row.get("trade_date")),
                code=self._stock_code(row.get("ts_code")),
                pe_ttm=self._float(row.get("pe_ttm")),
                pb=self._float(row.get("pb")),
                ps_ttm=self._float(row.get("ps_ttm")),
                pcf_ttm=self._float(row.get("pcf_ttm", row.get("pcf"))),
                dividend_yield=self._float(row.get("dv_ttm")),
                total_market_value=self._float(row.get("total_mv")),
                float_market_value=self._float(row.get("circ_mv")),
                available_date=self._next_business_date(row.get("trade_date")),
                data_version=self.data_version,
            )
            for row in rows
        ]

    def get_financials(self) -> List[FinancialRow]:
        """财务数据尚未接入。

        Raises:
            NotImplementedError: 总是抛出。`income`/`balancesheet`/`cashflow`/
                `fina_indicator` 需要额外的 Tushare 权限，未开通时强行调用只会得到
                空数据，因此这里明确失败而不是返回占位财报。
        """
        raise NotImplementedError(
            "Tushare financial endpoints require matching Tushare permissions; "
            "extend this provider with income, balancesheet, cashflow and fina_indicator mappings when the token scope is available."
        )

    def get_index_members(self, index_codes: List[str], trade_date: str) -> List[IndexMemberRow]:
        """指数成分尚未接入。

        Raises:
            NotImplementedError: 总是抛出。`index_weight`/`index_basic` 需要额外权限，
                在开通前调用方应改用 `FULL_MARKET` 全市场口径。
        """
        raise NotImplementedError(
            "Tushare index member endpoints require matching Tushare permissions; "
            "extend this provider with index_weight or index_basic mappings when the token scope is available."
        )

    def _pro_api(self):
        """延迟创建并缓存 Tushare Pro 客户端。

        先检查 token 再尝试导入包，错误顺序固定（token → 依赖），便于使用方按提示
        修复；成功后的客户端缓存在 `self._pro`，同一实例重复调用不会重复初始化。

        Returns:
            `tushare.pro_api(token)` 返回的客户端对象。

        Raises:
            RuntimeError: 未配置 token，或未安装 `tushare` 包（附带安装命令提示）。
        """
        if not self.token:
            raise RuntimeError("Tushare token is required. Set TUSHARE_TOKEN before using provider.active=tushare.")
        if self._pro is None:
            try:
                tushare = importlib.import_module("tushare")
            except ImportError as exc:
                raise RuntimeError("Tushare is not installed. Run: python -m pip install -r requirements.txt") from exc
            self._pro = tushare.pro_api(self.token)
        return self._pro

    def _to_records(self, data: Any) -> List[Dict[str, Any]]:
        """把 SDK 返回的 DataFrame 或列表统一成记录字典列表。

        Args:
            data: Tushare 返回值，可能是 `pandas.DataFrame`、记录列表或 `None`。

        Returns:
            记录列表；`None` 返回空列表，避免调用方对空响应做特殊判断。
        """
        if data is None:
            return []
        if hasattr(data, "to_dict"):
            return data.to_dict(orient="records")
        return list(data)

    def _compact_date(self, value: Any) -> str:
        """把日期值规整成 Tushare 需要的 `YYYYMMDD`（去掉短横线）。"""
        text = self._text(value)
        return text.replace("-", "")

    def _format_date(self, value: Any) -> str:
        """把 `YYYYMMDD` 或带短横线的日期转成 ISO `YYYY-MM-DD`。

        空值返回空串；不做严格校验，长度不足时按位置切片会得到异常结果，
        因此只用于 SDK 已保证格式的字段。
        """
        text = self._compact_date(value)
        if not text:
            return ""
        return "{}-{}-{}".format(text[:4], text[4:6], text[6:8])

    def _optional_date(self, value: Any) -> Optional[str]:
        """把可空日期字段转成 ISO 字符串；空值返回 `None`（如未退市股票的 `delist_date`）。"""
        text = self._text(value)
        if not text:
            return None
        return self._format_date(text)

    def _next_business_date(self, value: Any) -> str:
        """推算行情/估值的最早可用日：次一工作日。

        只跳过周六周日，不识别法定节假日，因此节前最后一个交易日会把可用日算到
        假期中的工作日；这只会让数据更晚可见，不会引入前视偏差。

        Args:
            value: 交易日，`YYYYMMDD` 或 `YYYY-MM-DD`。

        Returns:
            次一工作日的 ISO 日期字符串。
        """
        current = date.fromisoformat(self._format_date(value)) + timedelta(days=1)
        while current.weekday() >= 5:
            current += timedelta(days=1)
        return current.isoformat()

    def _stock_code(self, ts_code: Any) -> str:
        """从 `000001.SZ` 这类代码里取出 6 位股票代码。"""
        return self._text(ts_code).split(".")[0]

    def _map_status(self, value: Any) -> str:
        """把 Tushare 的 `L`/`D`/`P` 映射成 `listed`/`delisted`/`paused`，未知值原样返回。"""
        status = self._text(value)
        return {
            "L": "listed",
            "D": "delisted",
            "P": "paused",
        }.get(status, status)

    def _float(self, value: Any) -> float:
        """把可能为空或空串的数值转成 float；缺失统一记 0.0。

        用 0.0 而不是 `None` 是为了让下游列类型稳定，但"缺失"和"真实为 0"因此不可
        区分——因子层靠 `positive=True` 校验把 0 值当作缺失拦下。
        """
        if value is None or value == "":
            return 0.0
        return float(value)

    def _text(self, value: Any) -> str:
        """把任意值规整成去空白的字符串；`None` 返回空串（兼容 pandas 的 NaN 之外的缺失）。"""
        if value is None:
            return ""
        return str(value).strip()
