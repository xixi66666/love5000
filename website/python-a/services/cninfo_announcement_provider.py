"""巨潮公告 Provider 及交易所备用源，端点映射参考 a-stock-data V3.4.0。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from services.research_provider import (
    ResearchProviderError,
    UrlLibHttpClient,
    is_safe_external_url,
    success_block,
    validate_stock_code,
)


UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
ORG_MAP_URL = "https://www.cninfo.com.cn/new/data/szse_stock.json"
QUERY_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
SZSE_URL = "https://www.szse.cn/api/disc/announcement/annList"
EASTMONEY_URL = "https://np-anotice-stock.eastmoney.com/api/security/ann"


class CninfoAnnouncementProvider:
    provider_name = "cninfo"

    def __init__(self, http_client: Optional[Any] = None):
        self.http_client = http_client or UrlLibHttpClient()
        self._org_map = None

    def fetch(self, code: str, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        value = validate_stock_code(code)
        org_id = self._org_id(value)
        payload = self.http_client.post_form_json(
            QUERY_URL,
            data={
                "stock": "{},{}".format(value, org_id),
                "tabName": "fulltext",
                "pageSize": str(page_size),
                "pageNum": str(page),
                "column": "",
                "category": "",
                "plate": "",
                "seDate": "",
                "searchkey": "",
                "secid": "",
                "sortName": "",
                "sortType": "",
                "isHLtitle": "true",
            },
            headers={
                "User-Agent": UA,
                "Referer": "https://www.cninfo.com.cn/new/disclosure",
                "Origin": "https://www.cninfo.com.cn",
            },
            timeout=15,
        )
        items = []
        allowed = {"www.cninfo.com.cn"}
        for item in payload.get("announcements") or []:
            url = "https://www.cninfo.com.cn/new/disclosure/detail?annoId={}".format(
                item.get("announcementId") or ""
            )
            items.append(
                {
                    "title": str(item.get("announcementTitle") or ""),
                    "type": str(item.get("announcementTypeName") or ""),
                    "date": self._date(item.get("announcementTime")),
                    "url": url if is_safe_external_url(url, allowed) else None,
                }
            )
        total = int(payload.get("totalAnnouncement") or len(items))
        data_date = items[0]["date"] if items else None
        return success_block(
            self.provider_name,
            {
                "items": items,
                "page": page,
                "page_size": page_size,
                "has_more": page * page_size < total,
            },
            data_date=data_date,
        )

    def fetch_backup(self, code: str, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        value = validate_stock_code(code)
        if value.startswith(("0", "3")):
            return self._fetch_szse(value, page, page_size)
        return self._fetch_eastmoney(value, page, page_size)

    def _fetch_szse(self, code: str, page: int, page_size: int) -> Dict[str, Any]:
        payload = self.http_client.post_json(
            SZSE_URL,
            data={"channelCode": ["listedNotice_disc"], "pageSize": page_size, "pageNum": page, "stock": [code]},
            headers={"User-Agent": UA, "Referer": "https://www.szse.cn/disclosure/listed/notice/index.html"},
            timeout=15,
        )
        items = []
        allowed = {"disc.static.szse.cn"}
        for raw in payload.get("data") or []:
            path = str(raw.get("attachPath") or "")
            url = "https://disc.static.szse.cn/download" + path if path else ""
            items.append(
                {
                    "title": str(raw.get("title") or ""),
                    "type": str(raw.get("categoryName") or "公告"),
                    "date": str(raw.get("publishTime") or "")[:10],
                    "url": url if is_safe_external_url(url, allowed) else None,
                }
            )
        data_date = items[0]["date"] if items else None
        return success_block(
            "szse",
            {"items": items, "page": page, "page_size": page_size, "has_more": len(items) >= page_size},
            data_date=data_date,
        )

    def _fetch_eastmoney(self, code: str, page: int, page_size: int) -> Dict[str, Any]:
        payload = self.http_client.get_json(
            EASTMONEY_URL,
            params={
                "sr": "-1",
                "page_size": str(page_size),
                "page_index": str(page),
                "ann_type": "A",
                "client_source": "web",
                "stock_list": code,
                "f_node": "0",
                "s_node": "0",
            },
            headers={"User-Agent": UA},
            timeout=15,
        )
        items = []
        allowed = {"pdf.dfcfw.com"}
        for raw in (payload.get("data") or {}).get("list") or []:
            url = "https://pdf.dfcfw.com/pdf/H2_{}_1.pdf".format(raw.get("art_code") or "")
            items.append(
                {
                    "title": str(raw.get("title") or ""),
                    "type": "公告",
                    "date": str(raw.get("notice_date") or "")[:10],
                    "url": url if is_safe_external_url(url, allowed) else None,
                }
            )
        data_date = items[0]["date"] if items else None
        return success_block(
            "eastmoney",
            {"items": items, "page": page, "page_size": page_size, "has_more": len(items) >= page_size},
            data_date=data_date,
        )

    def _org_id(self, code: str) -> str:
        if self._org_map is None:
            payload = self.http_client.get_json(ORG_MAP_URL, headers={"User-Agent": UA}, timeout=15)
            self._org_map = {
                str(item.get("code") or ""): str(item.get("orgId") or "")
                for item in payload.get("stockList") or []
            }
        if self._org_map.get(code):
            return self._org_map[code]
        if code.startswith(("6", "9")):
            return "gssh0{}".format(code)
        if code.startswith("8"):
            return "gsbj0{}".format(code)
        return "gssz0{}".format(code)

    def _date(self, value: Any) -> str:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000).strftime("%Y-%m-%d")
        return str(value or "")[:10]
