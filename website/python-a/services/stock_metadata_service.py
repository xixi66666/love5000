from __future__ import annotations

import json
import os
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional


class TushareHttpClient:
    def __init__(
        self,
        token: Optional[str] = None,
        api_url: str = "https://api.tushare.pro",
        timeout_seconds: int = 15,
    ):
        self.token = (token if token is not None else os.environ.get("TUSHARE_TOKEN", "")).strip()
        self.api_url = api_url
        self.timeout_seconds = timeout_seconds

    def query(self, api_name: str, params: Optional[Dict[str, Any]] = None, fields: str = "") -> List[Dict[str, Any]]:
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
    api_url = "https://datacenter.eastmoney.com/securities/api/data/v1/get"

    def __init__(self, timeout_seconds: int = 15):
        self.timeout_seconds = timeout_seconds

    def fetch_boards(self, code: str) -> List[Dict[str, Any]]:
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
    def __init__(
        self,
        data_root: Path,
        client: Optional[Any] = None,
        eastmoney_client: Optional[Any] = None,
    ):
        self.data_root = Path(data_root)
        self.cache_root = self.data_root / "stock-metadata"
        self.client = client if client is not None else TushareHttpClient()
        self.eastmoney_client = eastmoney_client if eastmoney_client is not None else EastmoneyMetadataClient()

    def get_stock_metadata(self, code: str, fallback: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    def _fallback_metadata(self, code: str, fallback: Dict[str, Any], message: str) -> Dict[str, Any]:
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
        rows = sorted(boards, key=lambda row: int(row.get("BOARD_RANK") or 9999))
        result = []
        for row in rows:
            name = str(row.get("BOARD_NAME") or "").strip()
            if name and name not in result:
                result.append(name)
        return result

    def _stock_name_from_boards(self, boards: List[Dict[str, Any]]) -> str:
        for row in boards:
            name = str(row.get("SECURITY_NAME_ABBR") or "").strip()
            if name:
                return name
        return ""

    def _is_region_board(self, name: str) -> bool:
        return name.endswith("板块") and name not in ("创业板块", "科创板块")

    def _ts_code(self, code: str) -> str:
        suffix = "SH" if code.startswith(("6", "9")) else "SZ"
        return f"{code}.{suffix}"
