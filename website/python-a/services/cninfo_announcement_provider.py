"""巨潮公告主源与交易所备用源，端点映射参考 a-stock-data V3.4.0。

``CninfoAnnouncementProvider.fetch`` 查巨潮资讯的全量公告，``fetch_backup`` 按市场
选择备用源：0 / 3 开头（深市主板与创业板）走深交所公告接口，其余（沪市、北交所）
走东方财富公告接口。三个源都归一化成 ``{items, page, page_size, has_more}``，
每项为 ``{title, type, date, url}``，前端因此不必区分来源。

端点：``QUERY_URL``（巨潮全量公告查询，表单 POST）、``ORG_MAP_URL``（代码到巨潮
``orgId`` 的映射表）、``SZSE_URL``（深交所）、``EASTMONEY_URL``（东方财富）。
公告与 PDF 链接一律经 ``is_safe_external_url`` 白名单校验后才输出，只放行 https 且
域名精确匹配 ``www.cninfo.com.cn`` / ``disc.static.szse.cn`` / ``pdf.dfcfw.com``，
其余置 ``None``，避免把不可信地址渲染成可点击链接。

持久化：不写磁盘。机构映射表在实例上缓存一次（``_org_map``），首次查询会多一次网络
请求，之后复用；缓存不设过期，长期运行时若巨潮调整映射需要重启服务。

降级策略：网络与解析失败由 ``UrlLibHttpClient`` 抛 ``ResearchProviderError``，再由
``StockResearchService`` 捕获并切换备用源或返回失败块；``_org_id`` 在映射缺失时按
代码首位拼 ``gssh`` / ``gsbj`` / ``gssz`` 前缀兜底，保证新上市代码也能查询。
"""

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
    """巨潮公告与交易所备用公告的读取入口。

    实例持有 HTTP 客户端和一次性的机构映射缓存；缓存写入没有加锁，并发首查时可能
    重复拉取映射表，但两次结果一致，属于可接受的重复劳动。

    Attributes:
        provider_name: 写进 ``success_block`` 的来源标识，固定为 ``cninfo``。
    """

    provider_name = "cninfo"

    def __init__(self, http_client: Optional[Any] = None):
        """绑定 HTTP 客户端。

        Args:
            http_client: 需要支持 ``get_json`` / ``post_form_json`` / ``post_json``；
                为 ``None`` 时使用标准库实现，测试可注入桩以喂入固定报文。
        """
        self.http_client = http_client or UrlLibHttpClient()
        self._org_map = None

    def fetch(self, code: str, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """查询巨潮全量公告。

        请求体带一串空字符串字段，是巨潮接口要求的固定形态（分类、板块、日期区间全部
        留空表示不过滤）；``isHLtitle=true`` 让上游返回高亮标题。

        Args:
            code: 6 位代码，先校验再取机构 ID。
            page: 页码，从 1 开始，原样透传。
            page_size: 每页条数，原样透传；``has_more`` 由
                ``page * page_size`` 与上游 ``totalAnnouncement`` 比较得出。

        Returns:
            ``success_block`` 包装的 ``{items, page, page_size, has_more}``；
            ``data_date`` 取最新一条公告的日期。

        Raises:
            ValueError: 代码格式不合法。
            ResearchProviderError: 上游请求失败或返回非法 JSON。
        """
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
        """按市场选择交易所或东方财富的公告备用源。

        深市（0 / 3 开头）用深交所官方接口，数据最准；沪市与北交所在深交所接口没有
        对应数据，改用东方财富公告接口。两个分支返回同构结果，调用方无需判断。

        Args:
            code: 6 位代码。
            page: 页码，从 1 开始。
            page_size: 每页条数。

        Returns:
            ``success_block`` 包装的公告页，``provider`` 为 ``szse`` 或 ``eastmoney``。

        Raises:
            ValueError: 代码格式不合法。
            ResearchProviderError: 备用源请求失败或返回非法 JSON。
        """
        value = validate_stock_code(code)
        if value.startswith(("0", "3")):
            return self._fetch_szse(value, page, page_size)
        return self._fetch_eastmoney(value, page, page_size)

    def _fetch_szse(self, code: str, page: int, page_size: int) -> Dict[str, Any]:
        """查深交所公告列表。

        上游的 ``attachPath`` 只是相对路径，必须拼上 ``disc.static.szse.cn/download``
        才可下载；``publishTime`` 截前 10 位得到 ``YYYY-MM-DD``。深交所不回总数，
        因此 ``has_more`` 用“本页是否排满”近似，多翻一页可能得到空列表。

        Raises:
            ResearchProviderError: 请求失败或返回非法 JSON。
        """
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
        """查东方财富公告列表。

        PDF 地址由 ``art_code`` 套固定模板得到；``notice_date`` 截前 10 位得到
        ``YYYY-MM-DD``。东财同样不回总数，``has_more`` 同样按“本页排满”近似。

        Raises:
            ResearchProviderError: 请求失败或返回非法 JSON。
        """
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
        """取代码对应的巨潮机构 ID，缺失时按交易所拼兜底 ID。

        巨潮的查询接口要求 ``代码,orgId`` 成对传入。映射表第一次使用时整表拉取并缓存在
        实例上；表里查不到时按代码首位拼 ``gssh0`` / ``gsbj0`` / ``gssz0`` 前缀，这条
        规则与巨潮的 ID 命名一致，能让新上市或不在表里的代码继续可查。

        Args:
            code: 已校验的 6 位代码。

        Returns:
            机构 ID 字符串。

        Raises:
            ResearchProviderError: 首次拉取映射表时网络失败；此时调用方会切备用源。
        """
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
        """把巨潮的公告时间统一成 ``YYYY-MM-DD``。

        上游有时给毫秒时间戳（数字），有时给 ``YYYY-MM-DD HH:MM:SS`` 字符串，两种都
        处理；时间戳按本机时区转换，与页面展示的日期一致。

        Returns:
            日期字符串；无法判断时返回字符串的前 10 位（可能为空串）。
        """
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000).strftime("%Y-%m-%d")
        return str(value or "")[:10]
