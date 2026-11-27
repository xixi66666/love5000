"""股票研究数据的聚合层。

``StockResearchService`` 把腾讯行情、东方财富（估值 / 资金流 / 两融 / 股东 / 解禁 /
研报）、新浪资金流、巨潮公告与本地元数据拼成前端直接可用的 section：

- ``get_overview``：估值行情 + 行业概念，TTL 180 秒。
- ``get_capital``：资金流、融资融券、股东户数、解禁，TTL 1800 秒。
- ``get_events``：研报与公告分页，TTL 1800 秒。
- ``build_snapshot``：把三块压平成 ``{overview, capital, events}``，供 Obsidian 复盘
  与 AI 分析复用。

数据来源：全部来自构造时注入的 provider，本模块不直接发网络请求。持久化：只有进程内
缓存 ``_cache``，键为 ``(代码, section, 块名[, 页码, 页大小])``，值为 ``{time, value}``；
不落磁盘，进程重启即失效，缓存条目也不做淘汰（受股票数量约束）。

降级策略：每个数据块单独兜底，失败转 ``failure_block``，section 的 ``success`` 取
“任一子块成功”；只有入参非法（代码格式、``kind``、分页范围）才抛 ``ValueError``，
上游错误永远不外抛，保证部分数据源故障时页面仍然可用。
"""

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
    """带 TTL 缓存与逐块降级的研究数据聚合器。

    实例持有各 provider 引用、一份进程内缓存和一把锁；provider 本身无状态，因此
    整个实例可以跨请求线程共享。
    """

    # 行情与元数据盘中会变，用较短 TTL；资金流、两融、公告等日频数据用长 TTL。
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
        """绑定各数据源与缓存时钟。

        Args:
            tencent_provider: 提供 ``fetch(code)``，主行情源。
            eastmoney_provider: 提供估值、资金流、两融、股东、解禁与研报查询。
            sina_provider: 提供 ``fetch(code)``，资金流备用源。
            cninfo_provider: 提供 ``fetch`` / ``fetch_backup``，公告主源与备用源。
            metadata_service: 提供 ``get_stock_metadata(code, fallback=...)``。
            monotonic: 单调时钟函数，默认 ``time.monotonic``；测试可注入假时钟以验证
                TTL 过期，不必真的等待。
        """
        self.tencent_provider = tencent_provider
        self.eastmoney_provider = eastmoney_provider
        self.sina_provider = sina_provider
        self.cninfo_provider = cninfo_provider
        self.metadata_service = metadata_service
        self.monotonic = monotonic or time.monotonic
        self._cache: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
        self._cache_lock = threading.Lock()

    def get_overview(self, code: str, force: bool = False) -> Dict[str, Any]:
        """取估值行情与行业概念两块概览。

        估值优先腾讯，失败才回退东方财富；元数据块不参与回退链，自身已带三级降级。

        Args:
            code: 6 位代码。
            force: 为 ``True`` 时跳过缓存读取但仍写回新结果，用于用户手动刷新。

        Returns:
            ``{success, section, code, blocks}``，``blocks`` 含 ``valuation`` 与
            ``metadata`` 两个块。

        Raises:
            ValueError: 代码不是 6 位数字。
        """
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
        """取资金面四块：资金流、融资融券、股东户数、解禁。

        资金流优先东方财富、失败回退新浪；其余三块只有东方财富一个来源，失败即返回
        失败块，不会因此影响另外三块。

        Args:
            code: 6 位代码。
            force: 为 ``True`` 时绕过缓存。

        Returns:
            ``{success, section, code, blocks}``，``blocks`` 键为 ``fund_flow`` /
            ``margin`` / ``shareholders`` / ``lockups``。

        Raises:
            ValueError: 代码不是 6 位数字。
        """
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
        """取研报与公告事件，按页返回。

        分页参数进入缓存键，因此不同页各自缓存；``kind`` 允许只取其中一类，此时另一类
        不会发请求。

        Args:
            code: 6 位代码。
            kind: ``all`` / ``reports`` / ``announcements``。
            page: 页码，从 1 开始。
            page_size: 每页条数，限制在 1 到 20，避免一次拉取过多拖慢页面。
            force: 为 ``True`` 时绕过缓存。

        Returns:
            ``{success, section, code, blocks}``，``blocks`` 视 ``kind`` 含
            ``reports`` 与 ``announcements``。

        Raises:
            ValueError: 代码非法、``kind`` 越界、页码小于 1 或每页条数越界。
        """
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
        """把概览、资金面、事件压平成一份快照，供复盘与 AI 分析使用。

        ``load_missing=False`` 时资金面与事件只读已有缓存，不再为它们发起请求，适合在
        写复盘时避免因为某个上游超时把整次写入拖住；此时没有缓存的分块以空字典缺席。
        概览块始终走 ``get_overview``，未命中缓存时仍会请求行情，因为复盘离不开当天
        的价格与行业概念。

        Args:
            code: 6 位代码。
            load_missing: 是否允许为资金面与事件分块发起请求。

        Returns:
            ``{code, generated_at, overview, capital, events}``；每个分块内是
            ``_snapshot_blocks`` 压平后的字段，事件列表最多保留 5 条。

        Raises:
            ValueError: 代码不是 6 位数字。
        """
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
        """取行业概念块，并把元数据来源转成统一的数据块。

        ``fallback_used`` 的判定是“来源不是东方财富”：Tushare 与本地兜底拿到的行业
        概念精度都不如东方财富题材接口，页面据此提示数据可能滞后。

        Returns:
            成功时为 ``success_block``，元数据服务抛错时为 ``failure_block``；本方法
            不向外抛异常，避免一个可选信息拖垮整个概览。
        """
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
        """执行只做一次的信息块加载，失败时返回失败块。

        可重试性优先取 ``ResearchProviderError.retryable``，其他异常按可重试处理——
        未知异常更可能是临时故障，让页面提示“稍后重试”比断言“暂无数据”更诚实。

        Args:
            loader: 返回数据块的零参函数。
            label: 中文块名，会拼进“资金流数据暂不可用”这类提示。
        """
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
        """先走主源，失败再走备用源，并标记 ``fallback_used``。

        备用源返回的字典会被浅拷贝后写入 ``fallback_used=True``，不改动备用源内部的
        对象。两个源都失败时以备用源异常的可重试性为准；若备用源抛的是未知异常，
        退回主源的可重试性。

        Args:
            primary: 主源加载函数。
            fallback: 备用源加载函数。
            label: 中文块名，拼进失败提示。
        """
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
        """读穿缓存：命中且未过期直接返回，否则调用 ``loader`` 并写回。

        锁只包住字典读写，``loader`` 在锁外执行，慢请求不会阻塞其他股票的缓存读取；
        代价是并发首查可能重复请求同一数据，结果一致，属于以可用性换掉少量重复流量。
        缓存条目不做淘汰，``force=True`` 会绕过读但仍覆盖写。

        Args:
            key: 缓存键，必须能唯一标识一个数据块（含分页参数）。
            ttl: 过期秒数。
            force: 是否强制刷新。
            loader: 真正取数的零参函数，异常由调用方在外层兜底。

        Returns:
            缓存中的或新取到的数据块。
        """
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
        """只用缓存拼一个 section，不触发任何请求。

        键的前两段是代码与 section 名，第三段及以后是块名与分页参数；这里只取第三段
        当块名，分页参数被丢掉：同一 section 下不同页的缓存落到同一个键上，后写入的
        覆盖先写入的，因此 ``build_snapshot`` 拿到的是最近缓存过的那一页。

        Returns:
            有缓存时返回 ``_section`` 结构；一个块都没有时返回空字典。
        """
        blocks = {}
        with self._cache_lock:
            for key, cached in self._cache.items():
                if len(key) >= 3 and key[0] == code and key[1] == section:
                    blocks[str(key[2])] = cached["value"]
        return self._section(section, code, blocks) if blocks else {}

    def _section(self, name: str, code: str, blocks: Dict[str, Any]) -> Dict[str, Any]:
        """把多个数据块包成 section。

        ``success`` 取“任一子块成功”：只要有一块能用，页面就该显示这一块，其余块各自
        带自己的失败原因。
        """
        return {
            "success": any(block.get("success") for block in blocks.values()),
            "section": name,
            "code": code,
            "blocks": blocks,
        }

    def _snapshot_blocks(self, blocks: Dict[str, Any], item_limit: Optional[int] = None) -> Dict[str, Any]:
        """把数据块压平成“业务字段 + 少量元信息”的扁平字典。

        成功块的 ``data`` 会被展开到与 ``provider`` / ``data_date`` 同级，方便复盘模板
        直接取字段；失败块只保留 ``success`` 与 ``message``。``item_limit`` 用于截断
        ``items`` 数组（事件快照只留前几条），其余字段原样保留。
        """
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
