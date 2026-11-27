"""股票行业、板块与概念元数据的读取、缓存与降级。

``StockMetadataService.get_stock_metadata`` 是唯一入口，按“本地缓存 -> 东方财富题材
接口 -> Tushare -> 调用方兜底”的顺序取数，始终返回同一结构
``{code, name, industry, board, concepts, source, [message]}``。

数据来源与端点：东方财富 datacenter 的 ``RPT_F10_CORETHEME_BOARDTYPE``（板块与题材
排名）、Tushare 的 ``stock_basic`` / ``ths_hot`` / ``ths_member`` / ``concept_detail``。
Tushare 需要 ``TUSHARE_TOKEN``；它只用于元数据补全，与模型配置无关（模型和密钥一律
来自仓库根目录 ``model.properties``）。

磁盘布局：缓存写入 ``{data_root}/stock-metadata/{code}.json``，UTF-8、缩进 2、中文
不转义；读取用 ``utf-8-sig``，兼容手工编辑后带 BOM 的文件。缓存内的 ``code`` 与请求
不一致时视为失效并重新抓取，避免文件被改名或复制后张冠李戴。文件名直接用代码拼成
``{code}.json``，调用方（``StockResearchService``）已保证它是 6 位数字。

降级策略：任何一级失败都继续往下走，最终返回 ``source="fallback"`` 的兜底结构并把
两级错误拼进 ``message``，绝不向上抛异常。这是服务能在完全离线、没有 Tushare token
的机器上正常启动的前提。
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional


class TushareHttpClient:
    """Tushare Pro 的最小 JSON 客户端。

    只实现 ``query``：按 Tushare 约定的 ``{api_name, token, params, fields}`` 发 POST，
    再把 ``fields`` 与 ``items`` 两段结构还原成字典列表。不重试、不缓存，失败直接抛
    ``RuntimeError``，由 ``StockMetadataService`` 吞掉并降级。
    """

    def __init__(
        self,
        token: Optional[str] = None,
        api_url: str = "https://api.tushare.pro",
        timeout_seconds: int = 15,
    ):
        """记录 token 与端点。

        Args:
            token: Tushare token；为 ``None`` 时回退读取环境变量 ``TUSHARE_TOKEN``。
                这是本模块唯一读取的环境变量，且只影响可选的元数据补全。
            api_url: 接口地址，默认官方地址；测试可指向本地桩。
            timeout_seconds: 单次请求超时秒数。
        """
        self.token = (token if token is not None else os.environ.get("TUSHARE_TOKEN", "")).strip()
        self.api_url = api_url
        self.timeout_seconds = timeout_seconds

    def query(self, api_name: str, params: Optional[Dict[str, Any]] = None, fields: str = "") -> List[Dict[str, Any]]:
        """调用一个 Tushare 接口并把结果转成字典列表。

        Args:
            api_name: 接口名，如 ``stock_basic``。
            params: 查询参数字典，例如 ``{"ts_code": "600000.SH"}``。
            fields: 逗号分隔的字段串，Tushare 按该顺序返回 ``fields`` 数组。

        Returns:
            每行一个字典，键为字段名；无数据时为空列表。

        Raises:
            RuntimeError: 未配置 token、网络或超时失败、响应不是合法 JSON、
                或 Tushare 返回非 0 业务码（``code`` 为 ``None`` 时视为旧版成功响应）。
        """
        if not self.token:
            raise RuntimeError("TUSHARE_TOKEN 未配置，跳过 Tushare 元数据同步")
        payload = json.dumps(
            {
                "api_name": api_name,
                "token": self.token,
                "params": params or {},
                "fields": fields,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            self.api_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Tushare 请求失败：{exc}") from exc

        if data.get("code") not in (0, None):
            raise RuntimeError(f"Tushare 返回错误：{data.get('msg') or data.get('code')}")
        fields_list = data.get("data", {}).get("fields") or []
        items = data.get("data", {}).get("items") or []
        return [dict(zip(fields_list, item)) for item in items]


class EastmoneyMetadataClient:
    """东方财富题材（板块）接口客户端。

    只做一件事：按股票代码取该股票所属的板块与概念原始行，字段名保持上游大写形式，
    由 ``StockMetadataService`` 负责解释与过滤。
    """

    api_url = "https://datacenter.eastmoney.com/securities/api/data/v1/get"

    def __init__(self, timeout_seconds: int = 15):
        """记录超时时间。

        Args:
            timeout_seconds: 单次请求超时秒数。
        """
        self.timeout_seconds = timeout_seconds

    def fetch_boards(self, code: str) -> List[Dict[str, Any]]:
        """获取股票所属的板块与概念行。

        ``columns`` 只取需要的六个字段，减少响应体；``BOARD_RANK`` 升序返回，排名越靠前
        越能代表主营业务，``StockMetadataService`` 因此把第一条当行业。带
        ``Referer: emweb.securities.eastmoney.com`` 是因为该接口会校验来源页。

        Args:
            code: 6 位代码，直接拼进 ``filter``；格式由上层校验。

        Returns:
            上游 ``result.data`` 数组；字段名保持原样。

        Raises:
            RuntimeError: 网络失败、JSON 非法、``success`` 非真，或结果不是数组。
        """
        params = {
            "reportName": "RPT_F10_CORETHEME_BOARDTYPE",
            "columns": "SECUCODE,SECURITY_CODE,SECURITY_NAME_ABBR,BOARD_CODE,BOARD_NAME,IS_PRECISE,BOARD_RANK",
            "source": "WEB",
            "client": "WEB",
            "filter": f'(SECURITY_CODE="{code}")',
            "sortColumns": "BOARD_RANK",
            "sortTypes": "1",
        }
        url = f"{self.api_url}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
                "Referer": "https://emweb.securities.eastmoney.com/",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"东方财富题材接口请求失败：{exc}") from exc
        if not payload.get("success"):
            raise RuntimeError(f"东方财富题材接口返回错误：{payload.get('message')}")
        data = payload.get("result", {}).get("data") or []
        return data if isinstance(data, list) else []


class StockMetadataService:
    """行业、板块与概念元数据的读取、缓存与降级门面。

    两个取数客户端可在构造时注入，测试因此不需要联网。实例本身无进程内缓存，缓存只
    落在磁盘；并发抓取同一只股票可能重复写同一路径，内容一致，因此不额外加锁。
    """

    def __init__(
        self,
        data_root: Path,
        client: Optional[Any] = None,
        eastmoney_client: Optional[Any] = None,
    ):
        """绑定数据根目录与两个取数客户端。

        Args:
            data_root: 运行数据目录（生产为 ``obsidian-vault/A股AI``），缓存写入其下的
                ``stock-metadata/`` 子目录。
            client: Tushare 客户端；为 ``None`` 时新建默认实例（无 token 时自动跳过）。
            eastmoney_client: 东方财富题材客户端；显式传 ``None`` 表示不启用该源，
                此时 ``_fetch_from_eastmoney`` 会抛错并继续走 Tushare。
        """
        self.data_root = Path(data_root)
        self.cache_root = self.data_root / "stock-metadata"
        self.client = client if client is not None else TushareHttpClient()
        self.eastmoney_client = eastmoney_client if eastmoney_client is not None else EastmoneyMetadataClient()

    def get_stock_metadata(self, code: str, fallback: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """取股票元数据，按缓存、东方财富、Tushare、兜底的顺序降级。

        缓存命中要求文件可解析、是字典且 ``code`` 与请求一致；任一条件不满足就当作
        未命中并覆盖写入，不删除旧文件。成功取到的数据都会写缓存，兜底结果不写缓存，
        以便下次网络恢复后能自动补齐。

        Args:
            code: 6 位代码，直接用作缓存文件名。
            fallback: 调用方已有的名称、行业、板块与概念；用于兜底和补全缺失字段。

        Returns:
            统一结构字典；全部数据源都失败时 ``source="fallback"`` 且 ``message`` 里
            记录了两级错误。本方法不抛异常。
        """
        fallback = fallback or {}
        cache_path = self.cache_root / f"{code}.json"
        if cache_path.exists():
            try:
                data = json.loads(cache_path.read_text(encoding="utf-8-sig"))
                if isinstance(data, dict) and data.get("code") == code:
                    return data
            except json.JSONDecodeError:
                pass

        try:
            metadata = self._fetch_from_eastmoney(code, fallback)
            self._write_cache(cache_path, metadata)
            return metadata
        except Exception as exc:
            eastmoney_error = exc

        try:
            metadata = self._fetch_from_tushare(code, fallback)
            self._write_cache(cache_path, metadata)
            return metadata
        except Exception as exc:
            return self._fallback_metadata(code, fallback, f"{eastmoney_error}; {exc}")

    def _fetch_from_eastmoney(self, code: str, fallback: Dict[str, Any]) -> Dict[str, Any]:
        """用东方财富题材接口拼出元数据。

        板块行按 ``BOARD_RANK`` 升序，第一条作为行业，其余作为概念并过滤掉地域板块；
        概念最多保留 12 个，避免把几十个泛概念塞进复盘笔记。名称优先用调用方给的
        ``fallback``，其次用板块行里的股票简称，最后退回代码。

        Raises:
            RuntimeError: 客户端被显式禁用，或接口没有返回任何板块（此时应改走 Tushare）。
        """
        if self.eastmoney_client is None:
            raise RuntimeError("东方财富元数据客户端未启用")
        boards = self.eastmoney_client.fetch_boards(code)
        names = self._board_names(boards)
        if not names:
            raise RuntimeError("东方财富题材接口没有返回板块")
        industry = names[0]
        concepts = [name for name in names[1:] if not self._is_region_board(name)]
        return {
            "code": code,
            "name": str(fallback.get("name") or self._stock_name_from_boards(boards) or code),
            "industry": industry,
            "board": str(fallback.get("board") or "A股"),
            "concepts": concepts[:12],
            "source": "eastmoney",
        }

    def _fetch_from_tushare(self, code: str, fallback: Dict[str, Any]) -> Dict[str, Any]:
        """用 Tushare 基础信息与概念接口拼出元数据。

        ``stock_basic`` 返回的基本信息可能为空（新股或已退市），此时名称、行业、
        板块逐个回退到 ``fallback``；行业最终兜底为“待映射”，让上层能识别这是占位值。

        Raises:
            RuntimeError: 未配置 token 或请求失败。
        """
        ts_code = self._ts_code(code)
        basics = self.client.query(
            "stock_basic",
            {"ts_code": ts_code},
            "ts_code,name,exchange,list_date,list_status,industry",
        )
        basic = basics[0] if basics else {}
        concepts = self._fetch_concepts(ts_code)
        return {
            "code": code,
            "name": str(basic.get("name") or fallback.get("name") or code),
            "industry": str(basic.get("industry") or fallback.get("industry") or "待映射"),
            "board": str(basic.get("exchange") or fallback.get("board") or "A股"),
            "concepts": concepts,
            "source": "tushare",
        }

    def _fetch_concepts(self, ts_code: str) -> List[str]:
        """从 Tushare 的三个概念接口收集概念名并去重。

        三个接口的可用性取决于账号积分，因此逐个尝试、单独吞掉异常：``ths_hot`` 给热门
        概念，``ths_member`` 与 ``concept_detail`` 给成分概念。任一接口失败只是少几个
        概念，不影响整体元数据；结果最多 12 个。
        """
        names: List[str] = []
        try:
            hot_rows = self.client.query("ths_hot", {"ts_code": ts_code}, "ts_code,ts_name,hot,concept")
            for row in hot_rows:
                for name in self._parse_concept_list(row.get("concept")):
                    if name not in names:
                        names.append(name)
        except Exception:
            pass
        for api_name in ("ths_member", "concept_detail"):
            try:
                params_key = "con_code" if api_name == "ths_member" else "ts_code"
                rows = self.client.query(
                    api_name,
                    {params_key: ts_code},
                    "ts_code,name,con_code,con_name,concept_name",
                )
            except Exception:
                continue
            for row in rows:
                name = str(row.get("name") or row.get("concept_name") or "").strip()
                if name and name not in names:
                    names.append(name)
        return names[:12]

    def _fallback_concepts(self, fallback: Dict[str, Any]) -> List[str]:
        """把调用方给的兜底概念规范成去重、去空的字符串列表。

        只接受 ``list``：调用方偶尔会把整段 JSON 字符串塞进来，这里宁可丢概念也不把
        原始字符串当概念名写进复盘笔记。
        """
        concepts = fallback.get("concepts")
        if not isinstance(concepts, list):
            return []
        result = []
        for item in concepts:
            text = str(item).strip()
            if text and text not in result:
                result.append(text)
        return result

    def _parse_concept_list(self, value: Any) -> List[str]:
        """解析 Tushare 的概念字段，兼容数组、JSON 数组字符串与分隔符文本。

        上游同一字段在不同接口里可能是数组、``'["a","b"]'`` 这样的 JSON 文本，或
        逗号 / 顿号分隔的字符串；三种都能处理，解析失败时退回分隔符切分。
        """
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if not isinstance(value, str) or not value.strip():
            return []
        text = value.strip()
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass
        return [item.strip() for item in text.replace("，", ",").replace("、", ",").split(",") if item.strip()]

    def _write_cache(self, path: Path, metadata: Dict[str, Any]) -> None:
        """把元数据写入 ``stock-metadata/{code}.json``。

        先建父目录再整文件覆盖，不写入临时文件：缓存只是加速手段，进程在写入中途退出
        最多留下一个解析失败的缓存，下次调用会因 ``JSONDecodeError`` 重新抓取。
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    def _fallback_metadata(self, code: str, fallback: Dict[str, Any], message: str) -> Dict[str, Any]:
        """拼出所有数据源都失败时的兜底元数据。

        行业兜底为“待映射”、板块兜底为“A股”，其余取调用方传入的值；``message`` 保留
        两级错误原文，便于在页面或日志里定位是东方财富还是 Tushare 出的问题。
        """
        return {
            "code": code,
            "name": str(fallback.get("name") or code),
            "industry": str(fallback.get("industry") or "待映射"),
            "board": str(fallback.get("board") or "A股"),
            "concepts": self._fallback_concepts(fallback),
            "source": "fallback",
            "message": message,
        }

    def _board_names(self, boards: List[Dict[str, Any]]) -> List[str]:
        """按 ``BOARD_RANK`` 升序提取板块名并去重。

        排名缺失或为空时按 9999 处理，让这类行排到最后；上游若给出非数字排名，
        ``int()`` 会直接抛 ``ValueError``。重复名字只保留首次出现，
        因为同一板块可能在多个类型下重复返回。
        """
        rows = sorted(boards, key=lambda row: int(row.get("BOARD_RANK") or 9999))
        result = []
        for row in rows:
            name = str(row.get("BOARD_NAME") or "").strip()
            if name and name not in result:
                result.append(name)
        return result

    def _stock_name_from_boards(self, boards: List[Dict[str, Any]]) -> str:
        """从板块行里取股票简称，取不到时返回空串。"""
        for row in boards:
            name = str(row.get("SECURITY_NAME_ABBR") or "").strip()
            if name:
                return name
        return ""

    def _is_region_board(self, name: str) -> bool:
        """判断是否为地域板块。

        东方财富会把“上海板块”“深圳板块”这类地域标签混在概念里，对个股研究没有意义，
        因此以“板块”结尾的名称一律排除；“创业板块”“科创板块”虽然同以后缀结尾，但
        它们是板块属性而非地域，必须保留。
        """
        return name.endswith("板块") and name not in ("创业板块", "科创板块")

    def _ts_code(self, code: str) -> str:
        """把 6 位代码转成 Tushare 的 ``代码.交易所`` 形式：6 / 9 开头为 ``SH``，其余 ``SZ``。"""
        suffix = "SH" if code.startswith(("6", "9")) else "SZ"
        return f"{code}.{suffix}"
