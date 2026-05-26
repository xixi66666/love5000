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
            order by s.exchange, s.code
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
