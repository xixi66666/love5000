"""DuckDB 本地存储 `QuantRepository`。

量化数据的唯一落盘位置：`data_versions`（同步版本）+ 六张业务表（股票基础、交易日历、
日行情、估值、财务、指数成分）。所有表名、列名都先过 `TABLE_COLUMNS` 白名单，
SQL 里只出现白名单内的标识符，值一律走 `?` 参数绑定，避免拼接注入。

写入语义：`replace_table` 是"事务内清空再插入"，失败回滚；`append_rows` 直接追加、
不包事务，重复调用会产生重复行（调用方需先用 `delete_rows_for_codes` 去重）。
DuckDB 是嵌入式库，同一文件多进程写会互斥，因此服务内应尽量复用连接。
"""

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Iterable, List, Mapping, Optional

import duckdb


# 表名 → 允许的列顺序。既用于建表，也用于写入前校验：字段多一个或少一个都会报错，
# 防止 Provider 结构变更悄悄写进不匹配的列。金额/价格单位为元，比率字段为小数。
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
    """DuckDB 仓储：建表、整表替换、追加、按代码删除与查询。"""

    def __init__(self, db_path: Path):
        """打开（或创建）DuckDB 文件并确保表结构存在。

        Args:
            db_path: 数据库文件路径；父目录不存在时会自动创建。

        Raises:
            duckdb.Error: 文件被其他进程以写模式占用、路径不可写或文件损坏时抛出。
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = duckdb.connect(str(self.db_path))
        self.initialize_schema()

    def initialize_schema(self) -> None:
        """建表（幂等）。

        业务表用 `create table if not exists ... select ... where false` 建出带类型的
        零行空表，这样空库也能直接查询而不必先判断表是否存在；`data_versions` 的
        `created_at` 默认取当前时间戳，用作同步快照的排序依据。
        """
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
        """在事务内清空整表并写入新行。

        先校验列集合再开事务，列不匹配时不会改动任何数据；插入失败会 `rollback`
        并把原异常抛出，因此该表要么全旧、要么全新。`rows` 为空时会清空整表并返回 0。

        Args:
            table: 白名单内的表名（见 `TABLE_COLUMNS`）。
            rows: dataclass 或字典序列，字段集合必须与表定义完全一致。

        Returns:
            写入的行数。

        Raises:
            ValueError: 表名不在白名单，或列缺失/多余（消息里列出具体列名）。
            duckdb.Error: 写入失败（已回滚）。
        """
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

    def append_rows(self, table: str, rows: Iterable[object]) -> int:
        """追加写入，不清空已有数据，也不开显式事务。

        重复调用会产生重复行，调用方需要自己保证幂等（批量补行情时先按代码删除）。

        Args:
            table: 白名单内的表名。
            rows: dataclass 或字典序列；空序列返回 0 且不执行 SQL。

        Returns:
            写入的行数。

        Raises:
            ValueError: 表名不在白名单，或列缺失/多余。
        """
        table_name = self._table_name(table)
        items = [asdict(row) if is_dataclass(row) else dict(row) for row in rows]
        columns = self._column_names(table, items)
        if not items:
            return 0
        placeholders = ", ".join(["?"] * len(columns))
        column_sql = ", ".join(f'"{column}"' for column in columns)
        values = [tuple(item[column] for column in columns) for item in items]
        self.connection.executemany(f"insert into {table_name} ({column_sql}) values ({placeholders})", values)
        return len(items)

    def delete_rows_for_codes(self, table: str, code_column: str, codes: List[str]) -> None:
        """按代码批量删除行，用于分批补数据前的去重。

        Args:
            table: 白名单内的表名。
            code_column: 必须是该表已定义的列（例如 `daily_bar` 用 `code`），
                防止把任意字符串拼进 SQL。
            codes: 待删除的代码列表；空列表直接返回，不执行 SQL。

        Raises:
            ValueError: 表名不在白名单，或 `code_column` 不是该表的列。
        """
        if not codes:
            return
        table_name = self._table_name(table)
        if code_column not in TABLE_COLUMNS[table]:
            raise ValueError(f"Unknown column for {table}: {code_column}")
        placeholders = ", ".join(["?"] * len(codes))
        self.connection.execute(
            f'delete from {table_name} where "{code_column}" in ({placeholders})',
            codes,
        )

    def record_data_version(
        self,
        data_version: str,
        provider: str,
        start_date: str,
        end_date: str,
        created_at: Optional[str] = None,
    ) -> None:
        """记录一次同步的数据版本；同一 `data_version` 会被覆盖。

        `data_versions` 以 `data_version` 为主键，重复同步同一天只保留一行；
        当天快照查询（`latest_data_snapshot_for_day`）依赖 `created_at` 的日期部分。

        Args:
            data_version: 数据版本标识（如 `mock-2024-q1`、`akshare-20240527`）。
            provider: Provider 名称，用于按数据源区分快照。
            start_date: 本次同步的区间起（含）。
            end_date: 本次同步的区间止（含）。
            created_at: 可选的创建时间；为空时用数据库默认 `current_timestamp`。
                非空时强制转 timestamp，写错格式会由 DuckDB 抛错。
        """
        if created_at:
            self.connection.execute(
                "insert or replace into data_versions "
                "(data_version, provider, start_date, end_date, created_at) values (?, ?, ?, ?, cast(? as timestamp))",
                [data_version, provider, start_date, end_date, created_at],
            )
            return

        self.connection.execute(
            "insert or replace into data_versions (data_version, provider, start_date, end_date) values (?, ?, ?, ?)",
            [data_version, provider, start_date, end_date],
        )

    def latest_data_snapshot(self) -> Optional[Mapping[str, object]]:
        """返回最近一次同步的版本行，没有记录时返回 `None`。"""
        rows = self.fetch_dicts(
            "select data_version, provider, start_date, end_date, created_at "
            "from data_versions order by created_at desc limit 1"
        )
        return rows[0] if rows else None

    def latest_data_snapshot_for_day(self, provider: str, sync_date: str) -> Optional[Mapping[str, object]]:
        """返回指定 Provider 在某天（按 `created_at` 的日期）的最近一次同步记录。

        用于"当天已同步就复用"的短路逻辑：只比较日期部分，因此同一天多次同步会取
        时间最新的一条；没有记录返回 `None`。

        Args:
            provider: Provider 名称。
            sync_date: `YYYY-MM-DD` 日期字符串。
        """
        rows = self.fetch_dicts(
            "select data_version, provider, start_date, end_date, created_at "
            "from data_versions "
            "where provider = ? and cast(created_at as date) = cast(? as date) "
            "order by created_at desc limit 1",
            [provider, sync_date],
        )
        return rows[0] if rows else None

    def count_rows(self, table: str) -> int:
        """返回表的行数（用于状态展示与同步进度）。"""
        table_name = self._table_name(table)
        return self.connection.execute(f"select count(*) from {table_name}").fetchone()[0]

    def latest_data_version(self) -> str:
        """返回最近一次同步的 `data_version`；没有记录时返回空串。"""
        row = self.connection.execute("select data_version from data_versions order by created_at desc limit 1").fetchone()
        return row[0] if row else ""

    def fetch_dicts(self, query: str, params: Optional[List[object]] = None) -> List[Mapping[str, object]]:
        """执行查询并把结果行转成字典列表。

        Args:
            query: 含 `?` 占位符的 SQL；调用方负责用参数绑定，而不是拼接字符串。
            params: 与占位符顺序一致的参数列表，默认空。

        Returns:
            列名 → 值的字典列表；结果为空时返回空列表。

        Raises:
            duckdb.Error: SQL 语法错误、表不存在或参数个数不匹配时抛出。
        """
        cursor = self.connection.execute(query, params or [])
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def _table_name(self, table: str) -> str:
        """校验表名在白名单内并返回带引号的标识符。

        Raises:
            ValueError: 表名不在 `TABLE_COLUMNS`，例如注入式的字符串。
        """
        if table not in TABLE_COLUMNS:
            raise ValueError(f"Unknown table: {table}")
        return f'"{table}"'

    def _column_names(self, table: str, items: List[Mapping[str, object]]) -> List[str]:
        """按表定义确定写入列，并校验每行的字段集合完全一致。

        采用"集合完全相等"而不是取交集：多出或缺少字段都立即失败，避免 Provider 升级
        后静默丢列或写错列。错误信息会分别列出缺失与多余的列名。

        Args:
            table: 白名单内的表名。
            items: 待写入的行（字典形式）。

        Returns:
            该表的列顺序（与 `TABLE_COLUMNS` 一致）。

        Raises:
            ValueError: 任一行字段集合与该表定义不一致。
        """
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
