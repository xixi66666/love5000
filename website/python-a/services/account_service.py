"""交易账户的资金流水与账户快照读写服务。

对外提供 ``AccountService``：资金流水的增查（``list_capital_flows`` /
``add_capital_flow``）、本金累计（``current_principal``）、账户快照的写入与按日
查询（``add_account_snapshot`` / ``list_account_snapshots``），以及交易台首屏需要
的汇总（``dashboard``）。

数据来源与落盘位置：全部通过注入的 ``JsonStore`` 读写运行数据目录（生产为
``obsidian-vault/A股AI``）下的两个 JSON 数组文件——``capital_flows.json`` 存资金
流水，``account_snapshots.json`` 存账户快照，字段见各方法的 ``Returns``。

降级策略：本层不访问网络。入参非法抛 ``ValueError``（由 ``server.py`` 转成
``success=false`` 的中文提示），底层文件损坏由 ``JsonStore`` 抛 ``ValueError``；
两者都不会让进程退出。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .storage_service import JsonStore, filter_by_date, new_id, now_iso


# 运行数据目录下的文件名；根目录由 server.py 决定（生产为 obsidian-vault/A股AI）。
CAPITAL_FILE = "capital_flows.json"
SNAPSHOT_FILE = "account_snapshots.json"


class AccountService:
    """资金流水与账户快照的业务门面。

    只做字段校验、派生指标计算和查询组装，持久化全部交给注入的 ``JsonStore``。
    实例无状态，可被多个请求线程共享。
    """

    def __init__(self, store: JsonStore):
        """绑定底层 JSON 存储。

        Args:
            store: 指向运行数据目录的 ``JsonStore``，本服务所有文件名都相对其根路径解析。
        """
        self.store = store

    def list_capital_flows(self) -> List[Dict[str, Any]]:
        """读取全部资金流水。

        Returns:
            按写入顺序排列的流水行，字段为 id/date/type/amount/note/created_at；
            文件不存在时返回空列表而不是抛错。
        """
        return self.store.read_list(CAPITAL_FILE)

    def add_capital_flow(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """校验并追加一条资金流水。

        类型必须落在 ``initial`` / ``deposit`` / ``withdraw`` / ``adjustment``
        白名单内：它直接决定 ``current_principal`` 的加减方向，不能从前端原样透传，
        否则一个拼错的类型会让本金悄悄少算或多算。

        Args:
            payload: 请求体字典。``type``、``amount``、``date`` 必填；``note`` 可空；
                ``id`` 与 ``created_at`` 可由调用方指定，用于补录或导入历史数据。

        Returns:
            实际写入的行；未指定 ``id`` 时按已有流水总条数 + 1 生成
            ``cf_YYYYMMDD_NNN``。

        Raises:
            ValueError: 类型不在白名单、金额不是数字、日期为空，或底层 JSON 已损坏。
        """
        rows = self.list_capital_flows()
        flow_type = str(payload.get("type") or "").strip()
        if flow_type not in {"initial", "deposit", "withdraw", "adjustment"}:
            raise ValueError("资金流水类型必须是 initial、deposit、withdraw 或 adjustment")
        amount = self._number(payload.get("amount"), "金额")
        date_value = str(payload.get("date") or "").strip()
        if not date_value:
            raise ValueError("date is required")
        row = {
            "id": payload.get("id") or new_id("cf", date_value, len(rows) + 1),
            "date": date_value,
            "type": flow_type,
            "amount": amount,
            "note": str(payload.get("note") or "").strip(),
            "created_at": payload.get("created_at") or now_iso(),
        }
        return self.store.append_row(CAPITAL_FILE, row)

    def current_principal(self, through_date: Optional[str] = None) -> float:
        """按流水累计本金余额。

        初始本金、入金与手工校正记正，出金记负。截止日期用字符串比较
        ``row["date"] > through_date``，依赖 ``YYYY-MM-DD`` 定长格式，因此能重建
        “某天收盘时”的本金，历史快照不会因为后续出入金而漂移。

        Args:
            through_date: 截止日期 ``YYYY-MM-DD``；为空时累计全部流水。

        Returns:
            保留两位小数的本金合计；无任何流水时为 ``0.0``。

        Raises:
            ValueError: 历史流水里存在非数字金额（手工改坏文件时会走到这里）。
        """
        total = 0.0
        for row in self.list_capital_flows():
            if through_date and row.get("date", "") > through_date:
                continue
            amount = self._number(row.get("amount"), "金额")
            flow_type = row.get("type")
            if flow_type in {"initial", "deposit", "adjustment"}:
                total += amount
            elif flow_type == "withdraw":
                total -= amount
        return round(total, 2)

    def add_account_snapshot(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """校验并追加一条账户快照，同时算出账户层面的派生指标。

        派生规则：``principal`` 取 ``trade_date`` 当天的累计本金；
        ``account_profit`` 等于总资产减本金；``account_profit_rate`` 等于收益除以
        本金，本金为 0 时记 0 避免除零。截图解析与手工录入共用本方法，所以
        ``source``（默认 ``manual``）与 ``confirmed``（默认已确认）由调用方标注。

        Args:
            payload: 必填 ``trade_date``（兼容旧字段 ``date``）与 ``total_assets``；
                其余为可空数字或文本；``positions`` 不是数组时退化为空数组，
                不让一条脏数据挡住整条快照入库。

        Returns:
            写入的快照行；未指定 ``id`` 时按已有快照总条数 + 1 生成
            ``as_YYYYMMDD_NNN``。

        Raises:
            ValueError: 缺少交易日期，或总资产不是数字。
        """
        rows = self.store.read_list(SNAPSHOT_FILE)
        trade_date = str(payload.get("trade_date") or payload.get("date") or "").strip()
        if not trade_date:
            raise ValueError("trade_date is required")
        total_assets = self._number(payload.get("total_assets"), "总资产")
        principal = self.current_principal(trade_date)
        account_profit = round(total_assets - principal, 2)
        account_profit_rate = round(account_profit / principal, 4) if principal else 0.0
        row = {
            "id": payload.get("id") or new_id("as", trade_date, len(rows) + 1),
            "trade_date": trade_date,
            "broker": str(payload.get("broker") or "").strip(),
            "account_alias": str(payload.get("account_alias") or "").strip(),
            "total_assets": total_assets,
            "principal": principal,
            "account_profit": account_profit,
            "account_profit_rate": account_profit_rate,
            "daily_profit": self._optional_number(payload.get("daily_profit")),
            "floating_profit": self._optional_number(payload.get("floating_profit")),
            "market_value": self._optional_number(payload.get("market_value")),
            "available_cash": self._optional_number(payload.get("available_cash")),
            "withdrawable_cash": self._optional_number(payload.get("withdrawable_cash")),
            "position_ratio": self._optional_number(payload.get("position_ratio")),
            "positions": payload.get("positions") if isinstance(payload.get("positions"), list) else [],
            "source": str(payload.get("source") or "manual"),
            "confirmed": bool(payload.get("confirmed", True)),
            "note": str(payload.get("note") or "").strip(),
            "created_at": payload.get("created_at") or now_iso(),
        }
        return self.store.append_row(SNAPSHOT_FILE, row)

    def list_account_snapshots(self, date_value: Optional[str] = None) -> List[Dict[str, Any]]:
        """按交易日读取账户快照；``date_value`` 为空时返回全部。

        Returns:
            命中日期的快照行，顺序即写入顺序（最后一条为最新确认的一条）。
        """
        return filter_by_date(self.store.read_list(SNAPSHOT_FILE), date_value)

    def dashboard(self, date_value: str) -> Dict[str, Any]:
        """组装交易台首屏所需的当日视图。

        ``snapshot`` 取当日最后写入的一条（存储只追加，因此最后一条即最新确认的
        一条），当日没有快照时为 ``None``，前端据此显示“待录入”而不是 0 资产。

        Args:
            date_value: 交易日 ``YYYY-MM-DD``。

        Returns:
            ``{principal, snapshot, snapshots, capital_flows}``，其中 ``principal``
            与 ``capital_flows`` 都截止到该交易日。
        """
        snapshots = self.list_account_snapshots(date_value)
        latest = snapshots[-1] if snapshots else None
        return {
            "principal": self.current_principal(date_value),
            "snapshot": latest,
            "snapshots": snapshots,
            "capital_flows": filter_by_date(self.list_capital_flows(), date_value),
        }

    def _number(self, value: Any, label: str) -> float:
        """把必填数值字段转成浮点数，空值按中文字段名报错。

        Raises:
            ValueError: 值为空或无法解析；提示里带 ``label``，页面可以直接展示。
        """
        number = self._optional_number(value)
        if number is None:
            raise ValueError(f"{label}必须是数字")
        return number

    def _optional_number(self, value: Any) -> Optional[float]:
        """把可空数值字段转成保留 4 位小数的浮点数。

        ``None`` 与空字符串都视为“未填写”返回 ``None`` 而不是 0，前端因此能区分
        “没有数据”和“真实值为 0”。非空但无法解析时抛错，提示里带原始值。

        Raises:
            ValueError: 非空且无法转成数字。
        """
        if value in (None, ""):
            return None
        try:
            return round(float(value), 4)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"数值字段格式错误：{value}") from exc
