from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple

from services.research_provider import (
    ResearchProviderError,
    failure_block,
    now_iso,
    success_block,
    validate_stock_code,
)


class StockResearchService:
    OVERVIEW_TTL = 180
    DETAIL_TTL = 1800

    def __init__(
        self,
        tencent_provider: Any,
        eastmoney_provider: Any,
        sina_provider: Any,
        cninfo_provider: Any,
        metadata_service: Any,
        monotonic: Optional[Callable[[], float]] = None,
    ):
        self.tencent_provider = tencent_provider
        self.eastmoney_provider = eastmoney_provider
        self.sina_provider = sina_provider
        self.cninfo_provider = cninfo_provider
        self.metadata_service = metadata_service
        self.monotonic = monotonic or time.monotonic
        self._cache: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
        self._cache_lock = threading.Lock()

    def get_overview(self, code: str, force: bool = False) -> Dict[str, Any]:
        value = validate_stock_code(code)
        valuation = self._cached(
            (value, "overview", "valuation"),
            self.OVERVIEW_TTL,
            force,
            lambda: self._with_fallback(
                lambda: self.tencent_provider.fetch(value),
                lambda: self.eastmoney_provider.fetch_overview(value),
                "估值行情",
            ),
        )
        metadata = self._cached(
            (value, "overview", "metadata"),
            self.OVERVIEW_TTL,
            force,
            lambda: self._metadata_block(value),
        )
        return self._section("overview", value, {"valuation": valuation, "metadata": metadata})

    def get_capital(self, code: str, force: bool = False) -> Dict[str, Any]:
        value = validate_stock_code(code)
        specs = {
            "fund_flow": lambda: self._with_fallback(
                lambda: self.eastmoney_provider.fetch_fund_flow(value),
                lambda: self.sina_provider.fetch(value),
                "资金流",
            ),
            "margin": lambda: self._single(lambda: self.eastmoney_provider.fetch_margin(value), "融资融券"),
            "shareholders": lambda: self._single(
                lambda: self.eastmoney_provider.fetch_shareholders(value), "股东户数"
            ),
            "lockups": lambda: self._single(lambda: self.eastmoney_provider.fetch_lockups(value), "解禁数据"),
        }
        blocks = {}
        for name, loader in specs.items():
            blocks[name] = self._cached(
                (value, "capital", name),
                self.DETAIL_TTL,
                force,
                loader,
            )
        return self._section("capital", value, blocks)

    def get_events(
        self,
        code: str,
        kind: str = "all",
        page: int = 1,
        page_size: int = 10,
        force: bool = False,
    ) -> Dict[str, Any]:
        value = validate_stock_code(code)
        if kind not in ("all", "reports", "announcements"):
            raise ValueError("kind 必须是 all、reports 或 announcements")
        if page < 1:
            raise ValueError("page 必须从 1 开始")
        if page_size < 1 or page_size > 20:
            raise ValueError("page_size 必须在 1 到 20 之间")

        blocks = {}
        if kind in ("all", "reports"):
            blocks["reports"] = self._cached(
                (value, "events", "reports", page, page_size),
                self.DETAIL_TTL,
                force,
                lambda: self._single(
                    lambda: self.eastmoney_provider.fetch_reports(value, page=page, page_size=page_size),
                    "个股研报",
                ),
            )
        if kind in ("all", "announcements"):
            blocks["announcements"] = self._cached(
                (value, "events", "announcements", page, page_size),
                self.DETAIL_TTL,
                force,
                lambda: self._with_fallback(
                    lambda: self.cninfo_provider.fetch(value, page=page, page_size=page_size),
                    lambda: self.cninfo_provider.fetch_backup(value, page=page, page_size=page_size),
                    "公司公告",
                ),
            )
        return self._section("events", value, blocks)

    def build_snapshot(self, code: str, load_missing: bool = True) -> Dict[str, Any]:
        value = validate_stock_code(code)
        overview = self.get_overview(value, force=False)
        capital = self.get_capital(value, force=False) if load_missing else self._cached_section(value, "capital")
        events = (
            self.get_events(value, kind="all", page=1, page_size=10, force=False)
            if load_missing
            else self._cached_section(value, "events")
        )
        return {
            "code": value,
            "generated_at": now_iso(),
            "overview": self._snapshot_blocks(overview.get("blocks") or {}),
            "capital": self._snapshot_blocks((capital or {}).get("blocks") or {}),
            "events": self._snapshot_blocks((events or {}).get("blocks") or {}, item_limit=5),
        }

    def _metadata_block(self, code: str) -> Dict[str, Any]:
        try:
            metadata = self.metadata_service.get_stock_metadata(code, fallback={})
            provider = str(metadata.get("source") or "local")
            data = {
                "industry": metadata.get("industry"),
                "board": metadata.get("board"),
                "concepts": list(metadata.get("concepts") or [])[:12],
            }
            return success_block(provider, data, fallback_used=provider != "eastmoney")
        except Exception as exc:
            return failure_block("行业概念数据暂不可用：{}".format(exc), retryable=True)

    def _single(self, loader: Callable[[], Dict[str, Any]], label: str) -> Dict[str, Any]:
        try:
            return loader()
        except ResearchProviderError as exc:
            return failure_block("{}数据暂不可用".format(label), retryable=exc.retryable)
        except Exception:
            return failure_block("{}数据暂不可用".format(label), retryable=True)

    def _with_fallback(
        self,
        primary: Callable[[], Dict[str, Any]],
        fallback: Callable[[], Dict[str, Any]],
        label: str,
    ) -> Dict[str, Any]:
        try:
            return primary()
        except Exception as primary_error:
            try:
                result = dict(fallback())
                result["fallback_used"] = True
                return result
            except ResearchProviderError as fallback_error:
                return failure_block("{}数据暂不可用".format(label), retryable=fallback_error.retryable)
            except Exception:
                retryable = getattr(primary_error, "retryable", True)
                return failure_block("{}数据暂不可用".format(label), retryable=retryable)

    def _cached(
        self,
        key: Tuple[Any, ...],
        ttl: int,
        force: bool,
        loader: Callable[[], Dict[str, Any]],
    ) -> Dict[str, Any]:
        now = self.monotonic()
        with self._cache_lock:
            cached = self._cache.get(key)
            if cached and not force and now - cached["time"] <= ttl:
                return cached["value"]
        value = loader()
        with self._cache_lock:
            self._cache[key] = {"time": self.monotonic(), "value": value}
        return value

    def _cached_section(self, code: str, section: str) -> Dict[str, Any]:
        blocks = {}
        with self._cache_lock:
            for key, cached in self._cache.items():
                if len(key) >= 3 and key[0] == code and key[1] == section:
                    blocks[str(key[2])] = cached["value"]
        return self._section(section, code, blocks) if blocks else {}

    def _section(self, name: str, code: str, blocks: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "success": any(block.get("success") for block in blocks.values()),
            "section": name,
            "code": code,
            "blocks": blocks,
        }

    def _snapshot_blocks(self, blocks: Dict[str, Any], item_limit: Optional[int] = None) -> Dict[str, Any]:
        result = {}
        for name, block in blocks.items():
            if not block.get("success"):
                result[name] = {"success": False, "message": block.get("message")}
                continue
            data = dict(block.get("data") or {})
            if item_limit is not None and isinstance(data.get("items"), list):
                data["items"] = data["items"][:item_limit]
            result[name] = {
                "success": True,
                "provider": block.get("provider"),
                "data_date": block.get("data_date"),
                "fallback_used": bool(block.get("fallback_used")),
                **data,
            }
        return result
