from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Iterable, List, Mapping, Optional

import duckdb


TABLE_COLUMNS = {
    "stock_basic": ("code", "name", "exchange", "list_date", "delist_date", "status", "industry", "is_st"),
    "trade_calendar": ("trade_date", "is_open", "prev_trade_date", "next_trade_date", "is_month_end"),
    "daily_bar": (
        "trade_date",
        "code",
        "open",
        "high",
        "low",
        "close",
        "pre_close",
        "volume",
        "amount",
        "turnover_rate",
        "adj_factor",
        "limit_up",
        "limit_down",
        "suspend_flag",
        "available_date",
        "data_version",
    ),
    "valuation": (
        "trade_date",
        "code",
        "pe_ttm",
        "pb",
        "ps_ttm",
        "pcf_ttm",
        "dividend_yield",
        "total_market_value",
        "float_market_value",
        "available_date",
        "data_version",
    ),
    "financial": (
        "code",
        "report_period",
        "announce_date",
        "available_date",
        "revenue",
        "net_profit",
        "deducted_net_profit",
        "operating_cash_flow",
        "roe",
        "roa",
        "gross_margin",
        "net_margin",
        "debt_ratio",
        "data_version",
    ),
    "index_member": ("index_code", "code", "effective_date", "expire_date", "data_version"),
}


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
        self.connection.execute("create table if not exists stock_basic as select * from (select '' as code, '' as \"name\", '' as exchange, '' as list_date, null::varchar as delist_date, '' as status, '' as industry, false as is_st) where false")
        self.connection.execute("create table if not exists trade_calendar as select * from (select '' as trade_date, true as is_open, null::varchar as prev_trade_date, null::varchar as next_trade_date, false as is_month_end) where false")
        self.connection.execute("create table if not exists daily_bar as select * from (select '' as trade_date, '' as code, 0.0::double as open, 0.0::double as high, 0.0::double as low, 0.0::double as close, 0.0::double as pre_close, 0.0::double as volume, 0.0::double as amount, 0.0::double as turnover_rate, 0.0::double as adj_factor, 0.0::double as limit_up, 0.0::double as limit_down, false as suspend_flag, '' as available_date, '' as data_version) where false")
        self.connection.execute("create table if not exists valuation as select * from (select '' as trade_date, '' as code, 0.0::double as pe_ttm, 0.0::double as pb, 0.0::double as ps_ttm, 0.0::double as pcf_ttm, 0.0::double as dividend_yield, 0.0::double as total_market_value, 0.0::double as float_market_value, '' as available_date, '' as data_version) where false")
        self.connection.execute("create table if not exists financial as select * from (select '' as code, '' as report_period, '' as announce_date, '' as available_date, 0.0::double as revenue, 0.0::double as net_profit, 0.0::double as deducted_net_profit, 0.0::double as operating_cash_flow, 0.0::double as roe, 0.0::double as roa, 0.0::double as gross_margin, 0.0::double as net_margin, 0.0::double as debt_ratio, '' as data_version) where false")
        self.connection.execute("create table if not exists index_member as select * from (select '' as index_code, '' as code, '' as effective_date, null::varchar as expire_date, '' as data_version) where false")

    def replace_table(self, table: str, rows: Iterable[object]) -> int:
        table_name = self._table_name(table)
        items = [asdict(row) if is_dataclass(row) else dict(row) for row in rows]
        columns = self._column_names(table, items)
        placeholders = ", ".join(["?"] * len(columns))
        column_sql = ", ".join(f'"{column}"' for column in columns)
        values = [tuple(item[column] for column in columns) for item in items]
        try:
            self.connection.execute("begin transaction")
            self.connection.execute(f"delete from {table_name}")
            if values:
                self.connection.executemany(f"insert into {table_name} ({column_sql}) values ({placeholders})", values)
            self.connection.execute("commit")
            return len(items)
        except Exception:
            self.connection.execute("rollback")
            raise

    def record_data_version(self, data_version: str, provider: str, start_date: str, end_date: str) -> None:
        self.connection.execute(
            "insert or replace into data_versions (data_version, provider, start_date, end_date) values (?, ?, ?, ?)",
            [data_version, provider, start_date, end_date],
        )

    def latest_data_snapshot(self) -> Optional[Mapping[str, object]]:
        rows = self.fetch_dicts(
            "select data_version, provider, start_date, end_date, created_at "
            "from data_versions order by created_at desc limit 1"
        )
        return rows[0] if rows else None

    def latest_data_snapshot_for_day(self, provider: str, sync_date: str) -> Optional[Mapping[str, object]]:
        rows = self.fetch_dicts(
            "select data_version, provider, start_date, end_date, created_at "
            "from data_versions "
            "where provider = ? and cast(created_at as date) = cast(? as date) "
            "order by created_at desc limit 1",
            [provider, sync_date],
        )
        return rows[0] if rows else None

    def count_rows(self, table: str) -> int:
        table_name = self._table_name(table)
        return self.connection.execute(f"select count(*) from {table_name}").fetchone()[0]

    def latest_data_version(self) -> str:
        row = self.connection.execute("select data_version from data_versions order by created_at desc limit 1").fetchone()
        return row[0] if row else ""

    def fetch_dicts(self, query: str, params: Optional[List[object]] = None) -> List[Mapping[str, object]]:
        cursor = self.connection.execute(query, params or [])
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def _table_name(self, table: str) -> str:
        if table not in TABLE_COLUMNS:
            raise ValueError(f"Unknown table: {table}")
        return f'"{table}"'

    def _column_names(self, table: str, items: List[Mapping[str, object]]) -> List[str]:
        expected_columns = TABLE_COLUMNS[table]
        expected_set = set(expected_columns)
        for item in items:
            actual_set = set(item.keys())
            if actual_set != expected_set:
                missing = sorted(expected_set - actual_set)
                unexpected = sorted(actual_set - expected_set)
                details = []
                if missing:
                    details.append(f"missing columns: {', '.join(missing)}")
                if unexpected:
                    details.append(f"unexpected columns: {', '.join(unexpected)}")
                raise ValueError(f"Invalid columns for {table}: {'; '.join(details)}")
        return list(expected_columns)
