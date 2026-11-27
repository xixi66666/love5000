"""选股池服务 `UniverseService`。

按指数成分与可交易性过滤出当日可评分、可买入的股票池。三道边界都在 SQL 里落实：

1. 成分区间：`index_member.effective_date <= 决策日 < expire_date`，避免用"今天的
   成分股"回测历史（幸存者偏差）。
2. 防前视：20 日均额只用 `available_date <= 决策日` 的行情，最近一根 K 线也只取
   `trade_date <= 决策日 and available_date <= 决策日`，不会读到当天收盘后才有的数据。
3. 单位：`min_avg_amount_20d` 与 `daily_bar.amount` 同一单位（AkShare 为元，
   Tushare 为千元），换 Provider 时要同步改阈值。

`index_codes` 传 `FULL_MARKET` 或 `ALL` 时跳过指数成分表、直接取全部在市股票。
查询返回后，`build_universe` 再在 Python 侧按上市天数、ST、停牌与 20 日均额阈值
逐行过滤，命中不满足条件的股票不会进入评分。
"""

from datetime import date
from typing import Dict, List

from quant.storage.repository import QuantRepository


class UniverseService:
    """构造按指数成分与流动性过滤的股票池。"""

    def __init__(self, repository: QuantRepository):
        """注入本地仓储。

        Args:
            repository: 已同步 `stock_basic`/`index_member`/`daily_bar` 的仓储；表为空时
                得到空股票池而不是异常。
        """
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
        """按给定条件筛出当日股票池。

        Args:
            trade_date: 决策日（ISO 日期），所有 SQL 的时间条件都以它为准。
            index_codes: 指数代码列表；含 `FULL_MARKET`/`ALL`（大小写不敏感）时取全市场。
            min_listed_days: 最少上市自然日数，用于剔除次新股。
            min_avg_amount_20d: 20 日日均成交额下限，单位与 `daily_bar.amount` 一致。
            include_st: 是否保留 ST/*ST；`False` 时过滤。
            exclude_suspended: 是否剔除停牌股；最近一根 K 线缺失或 `suspend_flag` 为真
                都视为不可交易（缺失比"未知"更保守）。

        Returns:
            行字典列表，含 `code`/`name`/`exchange`/`list_date`/`industry`/`is_st`、
            `avg_amount_20d`、`suspend_flag`，并附加 `listed_days`（自然日，已按决策日计算）。
            空指数列表直接返回空列表。

        Raises:
            ValueError: `trade_date` 或 `list_date` 不是合法 ISO 日期时由
                `date.fromisoformat` 抛出。
        """
        if not index_codes:
            return []

        normalized_codes = {str(code).upper() for code in index_codes}
        use_full_market = bool(normalized_codes & {"FULL_MARKET", "ALL"})
        member_pool_sql = self._member_pool_sql(len(index_codes), use_full_market)
        member_params = [] if use_full_market else [*index_codes, trade_date, trade_date]

        rows = self.repository.fetch_dicts(
            f"""
            with member_pool as (
                {member_pool_sql}
            ),
            amount_20d as (
                select code, avg(amount) as avg_amount_20d
                from (
                    select code, amount,
                           row_number() over (partition by code order by trade_date desc) as rn
                    from daily_bar
                    where available_date <= ?
                )
                where rn <= 20
                group by code
            ),
            latest_bar as (
                select code, suspend_flag
                from (
                    select code, suspend_flag,
                           row_number() over (partition by code order by trade_date desc) as rn
                    from daily_bar
                    where trade_date <= ?
                      and available_date <= ?
                )
                where rn = 1
            )
            select s.code, s.name, s.exchange, s.list_date, s.industry, s.is_st,
                   coalesce(a.avg_amount_20d, 0) as avg_amount_20d,
                   b.suspend_flag as suspend_flag
            from stock_basic s
            join member_pool m on s.code = m.code
            left join amount_20d a on s.code = a.code
            left join latest_bar b on s.code = b.code
            order by s.exchange, s.code
            """,
            [*member_params, trade_date, trade_date, trade_date],
        )
        trade_day = date.fromisoformat(trade_date)
        result = []
        for row in rows:
            listed_days = (trade_day - date.fromisoformat(str(row["list_date"]))).days
            if listed_days < min_listed_days:
                continue
            if not include_st and row["is_st"]:
                continue
            if exclude_suspended and (row["suspend_flag"] is None or row["suspend_flag"]):
                continue
            if float(row["avg_amount_20d"]) < min_avg_amount_20d:
                continue
            result.append({
                **row,
                "listed_days": listed_days,
            })
        return result

    def _member_pool_sql(self, index_code_count: int, use_full_market: bool) -> str:
        """返回成分池的 SQL 片段（不含参数值）。

        只拼接占位符个数，指数代码本身始终以 `?` 绑定，避免 SQL 注入；调用方需要
        按 `[指数代码..., 决策日, 决策日]` 的顺序补参数。

        Args:
            index_code_count: `index_codes` 的长度，用于生成同样数量的占位符。
            use_full_market: 为真时返回"全部在市股票"，忽略指数成分表。

        Returns:
            可直接嵌入 CTE 的 `select ...` 语句片段。
        """
        if use_full_market:
            return "select code from stock_basic where status = 'listed'"

        placeholders = ", ".join(["?"] * index_code_count)
        return f"""
                select distinct code
                from index_member
                where index_code in ({placeholders})
                  and effective_date <= ?
                  and (expire_date is null or expire_date > ?)
        """
