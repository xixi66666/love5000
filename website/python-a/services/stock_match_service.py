"""股票名称到代码的匹配服务。

对外提供 ``StockMatchService``：``match_name`` 把用户输入的中文名称解析成代码，
``confirm_mapping`` 保存人工确认的映射。候选来自两处——运行数据目录下的
``stock_name_mappings.json``（人工确认过的映射，逐行 ``{stock_name, stock_code}``）
和构造时注入的种子行（``server.py`` 用自选股与元数据缓存拼出，只读不落盘）。

匹配顺序：先精确同名，再双向包含（模糊）。命中一条返回 ``matched``，命中多条返回
``multiple`` 交给前端选择，零命中返回 ``unmatched``；这三种结果都不抛异常，页面在
任何情况下都能继续渲染。只有 ``confirm_mapping`` 的名字或代码为空才抛
``ValueError``。

本模块不访问网络，除去掉首尾空格外不做名称规范化，匹配质量取决于种子数据的干净
程度；模糊规则是双向包含，名称过短时容易命中多个候选，这正是 ``multiple`` 存在的
原因。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .storage_service import JsonStore


# 人工确认映射的落盘文件名，位于运行数据目录（生产为 obsidian-vault/A股AI）。
MAPPING_FILE = "stock_name_mappings.json"


class StockMatchService:
    """名称匹配与人工映射持久化。

    实例无状态：候选列表每次调用都重新读取文件，另一个请求刚确认的映射不会因为
    缓存而失效。种子行在构造时固定，服务运行期间不会更新。
    """

    def __init__(self, store: JsonStore, seed_rows: Optional[List[Dict[str, Any]]] = None):
        """绑定存储与只读种子行。

        Args:
            store: 指向运行数据目录的 ``JsonStore``，人工映射文件相对其根路径解析。
            seed_rows: 可作为候选的 ``{stock_name, stock_code}`` 行；为 ``None`` 时
                只用人工映射，不会因此报错。
        """
        self.store = store
        self.seed_rows = seed_rows or []

    def match_name(self, stock_name: str) -> Dict[str, Any]:
        """把用户输入的中文股票名称解析成候选代码。

        空名称直接判为未匹配，避免空串的双向包含匹配命中全部候选。

        Args:
            stock_name: 用户输入的名称或简称，首尾空白会被去掉。

        Returns:
            ``{"status": "matched"|"multiple"|"unmatched", "candidates": [...]}``。
            ``matched`` 时还会把命中的那一行平铺到顶层（含 ``stock_name`` /
            ``stock_code``），前端不必再解包 ``candidates``。
        """
        name = stock_name.strip()
        if not name:
            return {"status": "unmatched", "candidates": []}
        candidates = self._all_candidates()
        exact = [item for item in candidates if item.get("stock_name") == name]
        if len(exact) == 1:
            return {"status": "matched", **exact[0], "candidates": exact}
        if len(exact) > 1:
            return {"status": "multiple", "candidates": exact}
        fuzzy = [item for item in candidates if name in item.get("stock_name", "") or item.get("stock_name", "") in name]
        if len(fuzzy) == 1:
            return {"status": "matched", **fuzzy[0], "candidates": fuzzy}
        if len(fuzzy) > 1:
            return {"status": "multiple", "candidates": fuzzy}
        return {"status": "unmatched", "candidates": []}

    def confirm_mapping(self, stock_name: str, stock_code: str) -> Dict[str, str]:
        """保存人工确认的名称到代码映射，同名旧记录被覆盖。

        先按 ``stock_name`` 过滤再追加，保证同一名称在文件中最多一行，避免反复
        确认同一只股票后候选列表里出现多个同名项。

        Args:
            stock_name: 名称，去空白后不得为空。
            stock_code: 代码；这里只校验非空，6 位格式由录入侧或元数据服务保证。

        Returns:
            实际写入的行 ``{"stock_name": ..., "stock_code": ...}``。

        Raises:
            ValueError: 名称或代码为空。
        """
        name = stock_name.strip()
        code = stock_code.strip()
        if not name or not code:
            raise ValueError("股票名称和代码都不能为空")
        rows = self.store.read_list(MAPPING_FILE)
        rows = [row for row in rows if row.get("stock_name") != name]
        row = {"stock_name": name, "stock_code": code}
        rows.append(row)
        self.store.write_list(MAPPING_FILE, rows)
        return row

    def _all_candidates(self) -> List[Dict[str, Any]]:
        """合并人工映射与种子行，并按 ``(代码, 名称)`` 去重。

        人工映射排在前面，重复时保留人工确认的那一行；该顺序同时决定
        ``multiple`` 结果中候选的展示顺序。
        """
        rows = []
        rows.extend(self.store.read_list(MAPPING_FILE))
        rows.extend(self.seed_rows)
        seen = set()
        unique = []
        for row in rows:
            key = (row.get("stock_code"), row.get("stock_name"))
            if key in seen:
                continue
            seen.add(key)
            unique.append(row)
        return unique
