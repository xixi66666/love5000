"""成交记账与 AI 截图解析草稿的状态机。

对外提供 ``TradeService``：``list_trades`` / ``add_trade`` 维护成交流水，
``create_parse_draft`` / ``list_parse_drafts`` / ``confirm_draft`` /
``reject_draft`` 管理截图解析草稿。

磁盘布局（运行数据目录，生产为 ``obsidian-vault/A股AI``）：

- ``trades.json``：成交流水，一行一笔，字段见 ``_build_trade``；编号形如
  ``tr_20240506_001``。
- ``parse_drafts.json``：解析草稿，``status`` 取 ``pending`` / ``confirming`` /
  ``confirmed`` / ``rejected``；草稿编号形如 ``pd_20240506_001``。

并发：``server.py`` 使用 ``ThreadingHTTPServer``，每个请求一个线程，读-改-写必须
串行。本模块用模块级 ``RLock`` 覆盖所有写路径（``add_trade``、
``create_parse_draft``、``confirm_draft``、``reject_draft``），只读查询不加锁。

降级策略：确认流程先把成交落盘、把草稿标成 ``confirming``，再标 ``confirmed``；
进程若在两步之间崩溃，重放确认时 ``_append_missing_trades`` 按编号跳过已写入的成交，
因此不会重复记账。字段非法一律抛 ``ValueError``，由 HTTP 处理器转成
``success=false`` 的中文提示。
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional, Set

from .storage_service import JsonStore, filter_by_date, new_id, now_iso


# 运行数据目录下的两个文件名；模块级可重入锁覆盖两个文件的读-改-写，
# 避免并发请求互相覆盖。用 RLock 是因为确认流程会调用内部方法再次进入临界区。
TRADES_FILE = "trades.json"
DRAFTS_FILE = "parse_drafts.json"
_TRADE_LOCK = threading.RLock()


class TradeService:
    """成交与解析草稿的业务门面。

    只做字段校验、编号生成与草稿状态流转，持久化交给注入的 ``JsonStore``。实例本身
    无状态，写方法共享模块级锁，因此多个 ``TradeService`` 实例之间也互斥。
    """

    def __init__(self, store: JsonStore):
        """绑定底层 JSON 存储。

        Args:
            store: 指向运行数据目录的 ``JsonStore``，``trades.json`` 与
                ``parse_drafts.json`` 都相对其根路径解析。
        """
        self.store = store

    def list_trades(self, date_value: Optional[str] = None) -> List[Dict[str, Any]]:
        """按交易日读取成交；``date_value`` 为空时返回全部。

        Returns:
            命中日期的成交行，顺序即写入顺序；文件不存在时为空列表。
        """
        return filter_by_date(self.store.read_list(TRADES_FILE), date_value)

    def add_trade(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """校验并追加一笔成交。

        在锁内重新读取已有编号再生成新编号，避免并发追加时两笔成交拿到同一个
        ``tr_YYYYMMDD_NNN``；调用方显式传入的 ``id`` 若已存在则拒绝写入。

        Args:
            payload: 请求体字典，``trade_datetime``、``side``、``price``、
                ``quantity``、``amount``、``stock_name`` 必填，其余可空。

        Returns:
            实际写入的成交行。

        Raises:
            ValueError: 必填字段缺失、数值非法、方向不在白名单，或编号重复。
        """
        with _TRADE_LOCK:
            rows = self.store.read_list(TRADES_FILE)
            existing_ids = {row.get("id") for row in rows if isinstance(row, dict)}
            row = self._build_trade(payload, len(rows) + 1, existing_ids)
            return self.store.append_row(TRADES_FILE, row)

    def _build_trade(self, payload: Dict[str, Any], sequence: int, existing_ids: Optional[Set[Any]] = None) -> Dict[str, Any]:
        """把请求体或解析结果规范成一条成交流水。

        规则：``trade_datetime`` 必填，``trade_date`` 缺省取前 10 个字符；
        ``side`` 走 ``_normalize_side`` 白名单；``price`` / ``amount`` 必填为数字，
        ``quantity`` 取整（股数不支持小数）；费用三项可空；``planned_trade`` 原样透传
        不做类型转换；``source`` 默认 ``manual``，AI 解析写入
        ``ai_parse``；``confirmed`` 默认已确认。

        Args:
            payload: 原始字典，键缺失按可空处理。
            sequence: 生成编号时的起始序号，调用方一般传“已有条数 + 1”。
            existing_ids: 已有成交编号集合；为 ``None`` 时不做唯一性检查（用于构造
                尚未入库的行）。

        Returns:
            补齐默认值后的成交行。

        Raises:
            ValueError: 缺少成交时间、方向非法、数值非法、缺少股票名称，或调用方
                指定的编号已存在。
        """
        trade_datetime = str(payload.get("trade_datetime") or "").strip()
        if not trade_datetime:
            raise ValueError("trade_datetime is required")
        trade_date = str(payload.get("trade_date") or trade_datetime[:10])
        row_id = payload.get("id")
        if row_id:
            if existing_ids is not None and row_id in existing_ids:
                raise ValueError(f"交易编号已存在：{row_id}")
        else:
            while True:
                row_id = new_id("tr", trade_date, sequence)
                if existing_ids is None or row_id not in existing_ids:
                    break
                sequence += 1
        row = {
            "id": row_id,
            "trade_datetime": trade_datetime,
            "trade_date": trade_date,
            "stock_code": str(payload.get("stock_code") or "").strip(),
            "stock_name": str(payload.get("stock_name") or "").strip(),
            "side": self._normalize_side(payload.get("side")),
            "price": self._number(payload.get("price"), "成交价格"),
            "quantity": int(self._number(payload.get("quantity"), "成交数量")),
            "amount": self._number(payload.get("amount"), "成交金额"),
            "fee": self._optional_number(payload.get("fee")),
            "stamp_tax": self._optional_number(payload.get("stamp_tax")),
            "transfer_fee": self._optional_number(payload.get("transfer_fee")),
            "reason": str(payload.get("reason") or "").strip(),
            "plan": str(payload.get("plan") or "").strip(),
            "emotion": str(payload.get("emotion") or "").strip(),
            "planned_trade": payload.get("planned_trade"),
            "source": str(payload.get("source") or "manual"),
            "confirmed": bool(payload.get("confirmed", True)),
            "created_at": payload.get("created_at") or now_iso(),
        }
        if not row["stock_name"]:
            raise ValueError("stock_name is required")
        return row

    def create_parse_draft(self, draft_type: str, trade_date: str, parsed: Dict[str, Any], warnings: List[str]) -> Dict[str, Any]:
        """保存一份待确认的截图解析草稿。

        草稿只入库不进账本，用户确认（``confirm_draft``）后才可能写入成交，这样模型
        识别错误不会直接污染交易记录。

        Args:
            draft_type: ``account_screenshot``（账户总览）或 ``trades_screenshot``
                （历史成交），只有后者会在确认时生成成交。
            trade_date: 草稿对应的交易日，用于生成编号与页面分组。
            parsed: 模型返回的原始字典，原样保存以便页面回显与人工修改。
            warnings: 解析期的告警（字段缺失、代码未识别等），原样保存。

        Returns:
            写入的草稿行，``status`` 为 ``pending``。

        Raises:
            ValueError: ``draft_type`` 不在白名单，或底层 JSON 损坏。
        """
        if draft_type not in {"account_screenshot", "trades_screenshot"}:
            raise ValueError("解析草稿类型错误")
        with _TRADE_LOCK:
            rows = self.store.read_list(DRAFTS_FILE)
            row = {
                "id": new_id("pd", trade_date, len(rows) + 1),
                "type": draft_type,
                "trade_date": trade_date,
                "status": "pending",
                "parsed": parsed,
                "warnings": warnings,
                "created_at": now_iso(),
            }
            return self.store.append_row(DRAFTS_FILE, row)

    def list_parse_drafts(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """按状态读取解析草稿；``status`` 为空时返回全部。

        Returns:
            命中的草稿行，顺序即写入顺序。
        """
        rows = self.store.read_list(DRAFTS_FILE)
        if status:
            return [row for row in rows if row.get("status") == status]
        return rows

    def confirm_draft(self, draft_id: str, confirmed_payload: Dict[str, Any]) -> Dict[str, Any]:
        """确认草稿并（对成交草稿）把成交写入账本。

        成交草稿的状态流转是 ``pending`` -> ``confirming`` -> ``confirmed``；账户草稿
        没有待写成交，直接 ``pending`` -> ``confirmed``。``confirming`` 是
        崩溃恢复点——成交已落盘但草稿还没标完成；再次确认时走同一状态分支，只补写
        缺失编号的成交并把草稿标为 ``confirmed``。已经是 ``confirmed`` 的草稿重复
        确认时原样返回首次结果，接口因此是幂等的。

        Args:
            draft_id: 草稿编号，如 ``pd_20240506_001``。
            confirmed_payload: 用户在页面上修正确认后的内容；账户草稿只记录不落账本，
                成交草稿读取其中的 ``trades`` 数组。

        Returns:
            ``{draft, created_trades}``；``draft`` 为更新后的草稿，``created_trades``
            为本次确认应写入的成交行。

        Raises:
            ValueError: 草稿不存在、当前状态不可确认、确认内容结构非法，或其中的成交
                字段不合法。
        """
        with _TRADE_LOCK:
            drafts = self.store.read_list(DRAFTS_FILE)
            draft = self._find_draft(drafts, draft_id)
            status = draft.get("status") or "pending"

            if status == "confirmed":
                return {"draft": draft, "created_trades": list(draft.get("created_trades") or [])}

            if status == "confirming":
                created_trades = list(draft.get("created_trades") or [])
                self._append_missing_trades(created_trades)
                draft["status"] = "confirmed"
                draft["confirmed_at"] = now_iso()
                self.store.write_list(DRAFTS_FILE, drafts)
                return {"draft": draft, "created_trades": created_trades}

            if status != "pending":
                raise ValueError("解析草稿当前状态不可确认")

            created_trades = self._build_created_trades(draft, confirmed_payload)
            draft["confirmed_payload"] = confirmed_payload
            draft["created_trades"] = created_trades
            if created_trades:
                draft["status"] = "confirming"
                self.store.write_list(DRAFTS_FILE, drafts)
                self._append_missing_trades(created_trades)
            draft["status"] = "confirmed"
            draft["confirmed_at"] = now_iso()
            self.store.write_list(DRAFTS_FILE, drafts)
            return {"draft": draft, "created_trades": created_trades}

    def reject_draft(self, draft_id: str) -> Dict[str, Any]:
        """驳回草稿，仅允许在 ``pending`` 状态操作。

        已驳回的草稿重复驳回时直接返回，保证按钮可重复点击；已确认的草稿不能驳回，
        因为对应成交可能已经写入账本。

        Returns:
            更新后的草稿行。

        Raises:
            ValueError: 草稿不存在或当前状态不是 ``pending`` / ``rejected``。
        """
        with _TRADE_LOCK:
            drafts = self.store.read_list(DRAFTS_FILE)
            draft = self._find_draft(drafts, draft_id)
            status = draft.get("status") or "pending"
            if status == "rejected":
                return draft
            if status != "pending":
                raise ValueError("解析草稿当前状态不可驳回")
            draft["status"] = "rejected"
            draft["rejected_at"] = now_iso()
            self.store.write_list(DRAFTS_FILE, drafts)
            return draft

    def _build_created_trades(self, draft: Dict[str, Any], confirmed_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """根据确认后的内容构造待写入的成交行（不落盘）。

        账户草稿不产生成交，直接返回空列表。成交草稿逐条走 ``_build_trade``，并把
        ``source`` 固定为 ``ai_parse``；每构造一条就把编号加入集合，使同一批里生成的
        编号也不会相撞。

        Returns:
            已校验、尚未写入 ``trades.json`` 的成交行列表。

        Raises:
            ValueError: 确认内容不是对象、``trades`` 不是数组，或其中某条成交字段非法。
        """
        if draft.get("type") != "trades_screenshot":
            return []
        if not isinstance(confirmed_payload, dict):
            raise ValueError("确认内容必须是对象")
        trades = confirmed_payload.get("trades") or []
        if not isinstance(trades, list):
            raise ValueError("trades 必须是数组")
        existing_trades = self.store.read_list(TRADES_FILE)
        existing_ids = {row.get("id") for row in existing_trades if isinstance(row, dict)}
        created_trades = []
        for index, trade in enumerate(trades, start=1):
            if not isinstance(trade, dict):
                raise ValueError("交易记录必须是对象")
            item = dict(trade)
            item["source"] = "ai_parse"
            built = self._build_trade(item, len(existing_trades) + index, existing_ids)
            created_trades.append(built)
            existing_ids.add(built["id"])
        return created_trades

    def _append_missing_trades(self, created_trades: List[Dict[str, Any]]) -> None:
        """把尚未入库的成交追加到账本，按编号去重。

        这是确认流程的幂等保证：崩溃后重放确认时，已写入的编号会被跳过，不会重复
        记账。整批一次写入而不是逐条追加，减少中间态。

        Args:
            created_trades: ``_build_created_trades`` 或草稿中记录的待写成交。
        """
        if not created_trades:
            return
        existing_trades = self.store.read_list(TRADES_FILE)
        known_ids = {row.get("id") for row in existing_trades if isinstance(row, dict)}
        missing = []
        for row in created_trades:
            row_id = row.get("id")
            if row_id is not None and row_id in known_ids:
                continue
            missing.append(row)
            if row_id is not None:
                known_ids.add(row_id)
        if missing:
            self.store.write_list(TRADES_FILE, existing_trades + missing)

    def _find_draft(self, drafts: List[Dict[str, Any]], draft_id: str) -> Dict[str, Any]:
        """在草稿列表中按编号查找，返回行本身（可变，用于就地更新状态）。

        Raises:
            ValueError: 找不到对应草稿，提示“解析草稿不存在”。
        """
        for draft in drafts:
            if draft.get("id") == draft_id:
                return draft
        raise ValueError("解析草稿不存在")

    def _normalize_side(self, value: Any) -> str:
        """把交易方向归一成 ``buy`` / ``sell``。

        兼容人工录入与视觉模型输出的中英文写法，统一转小写后比对，避免“买入”与
        “buy”在账本里混成两种方向。

        Raises:
            ValueError: 不在买入或卖出的白名单内。
        """
        text = str(value or "").strip().lower()
        if text in {"buy", "买", "买入"}:
            return "buy"
        if text in {"sell", "卖", "卖出"}:
            return "sell"
        raise ValueError("交易方向必须是买入或卖出")

    def _number(self, value: Any, label: str) -> float:
        """把必填数值字段转成浮点数，空值按中文字段名报错。

        Raises:
            ValueError: 值为空或无法解析。
        """
        number = self._optional_number(value)
        if number is None:
            raise ValueError(f"{label}必须是数字")
        return number

    def _optional_number(self, value: Any):
        """把可空数值字段转成保留 4 位小数的浮点数。

        ``None`` 与空字符串视为未填写返回 ``None``，让“没有手续费”和“手续费为 0”
        在页面上可区分；非空但无法解析时抛错并带上原始值。

        Raises:
            ValueError: 非空且无法转成数字。
        """
        if value in (None, ""):
            return None
        try:
            return round(float(value), 4)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"数值字段格式错误：{value}") from exc
