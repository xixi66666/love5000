"""Obsidian 知识图谱节点与双链生成。

对外提供 ``ObsidianKnowledgeGraphService``：``build_review_context`` 把股票元数据、
行情快照和复盘正文归纳成一组带分类的节点并生成双链；``write_concept_notes`` 把
节点写成 Obsidian 笔记并回链到个股笔记；``markdown_section`` 生成要嵌进复盘笔记的
“知识图谱链接”小节。

节点分类与目录名由 ``CATEGORY_FOLDERS`` 固定：股票、行业、概念、技术形态、风险模式、
交易错误、观察计划。落盘位置为
``{vault_root}/知识图谱/{分类目录}/{分类目录}-{名称}.md``。

数据来源：股票元数据（``StockMetadataService``）、行情快照（腾讯 / 东方财富）与用户
在复盘里填写的文本；``RULES`` 是从复盘措辞反推节点的本地关键词表，不调用模型。

降级策略：本模块不吞异常，``OSError`` 由 ``server.py`` 转成 ``success=false``；
``_number`` 把无法解析的阈值输入当作 0，使“高换手 / 疑似派发”这类规则在行情缺失时
安静地不触发，而不是让整次复盘写入失败。

Windows 兼容：节点标题同时是文件名和 Obsidian 链接目标，落盘前必须经
``_safe_filename`` 过滤 Windows 文件名非法字符（尖括号、冒号、双引号、正斜杠、
反斜杠、竖线、问号、星号）与 C0 控制字符（0x00–0x1f），替换为 ``-`` 后截断到
120 字符；过滤后的文件名与链接文本必须完全一致，否则双链会断。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set

from .storage_service import now_iso


class ObsidianKnowledgeGraphService:
    """知识图谱节点的归纳、落盘与双链生成。

    实例只保存 Vault 根目录；``CATEGORY_FOLDERS`` 与 ``RULES`` 是类级只读常量，
    多个请求线程共享不会互相干扰。
    """

    # 节点分类 -> Obsidian 目录名；目录名同时作为节点标题前缀（见 _node_title），
    # 因此改这里的值会让已有双链指向新文件名，属于破坏性变更。
    CATEGORY_FOLDERS = {
        "stock": "股票",
        "industry": "行业",
        "concept": "概念",
        "technical": "技术形态",
        "risk": "风险模式",
        "mistake": "交易错误",
        "plan": "观察计划",
    }

    # 复盘措辞 -> 节点的关键词表：命中任意一个关键词即生成对应节点。
    # 字典顺序决定 markdown_section 中链接的排列顺序；同义词越多命中率越高，
    # 但过短的词（如“追高”“情绪”）容易误判，加词需要配合真实复盘样本回归。
    RULES = {
        "technical": [
            ("多头排列", ["多头排列", "均线多头"]),
            ("跌破均线", ["跌破5日", "跌破10日", "跌破30日", "跌破均线"]),
            ("高位震荡", ["高位震荡", "高位回落", "上影线"]),
            ("缩量回踩", ["缩量回踩", "缩量调整"]),
            ("放量突破", ["放量突破", "阳包阴"]),
        ],
        "risk": [
            ("高换手", ["高换手", "换手率", "天量"]),
            ("疑似派发", ["疑似派发", "派发", "出货"]),
            ("追涨风险", ["追涨", "追高"]),
            ("放量滞涨", ["放量滞涨", "堆量滞涨"]),
            ("多杀多", ["多杀多", "承接不足"]),
        ],
        "mistake": [
            ("追高", ["追高", "追涨"]),
            ("没有止损条件", ["没有止损", "止损条件", "跌破条件"]),
            ("情绪化交易", ["情绪", "冲动"]),
            ("仓位过重", ["仓位太满", "仓位过重", "满仓"]),
        ],
        "plan": [
            ("等待右侧确认", ["右侧确认", "等待确认"]),
            ("观察缩量回踩", ["缩量回踩", "缩量且", "缩量"]),
            ("复核板块共振", ["板块共振", "板块强度", "联动性"]),
            ("设置反证条件", ["反证条件", "失效条件"]),
        ],
    }

    def __init__(self, vault_root: Path):
        """绑定 Vault 根目录。

        Args:
            vault_root: Obsidian Vault 根目录（生产为 ``obsidian-vault/A股AI``），
                节点笔记写到其下的 ``知识图谱/`` 子目录。
        """
        self.vault_root = Path(vault_root)

    def build_review_context(
        self,
        metadata: Dict[str, Any],
        quote_snapshot: Dict[str, Any],
        review_fields: Dict[str, Any],
    ) -> Dict[str, Any]:
        """把一次个股复盘归纳成知识图谱节点与双链。

        节点来源分三类：

        - 元数据：个股本身、行业、概念；``待映射`` 与空行业被跳过。
        - 行情：均线状态（``等待确认`` 跳过）、风险标签（``未知`` / ``待确认``
          跳过），以及换手率不低于 20% 或换手分位不低于 85% 时的“高换手”、
          派发分不低于 70 时的“疑似派发”。
        - 复盘文本：按 ``RULES`` 关键词命中技术形态、风险模式、交易错误与观察计划。

        最后按 ``(分类, 名称)`` 去重并生成双链，避免同一节点重复出现。

        Args:
            metadata: 股票元数据，读取 ``stock_code`` / ``code``、``stock_name`` /
                ``name``、``industry``、``concepts``。
            quote_snapshot: 行情快照，读取 ``ma_state``、``risk``、
                ``turnover_rate``、``turnover_percentile``、``distribution_score``。
            review_fields: 复盘表单字段，所有值拼成一段文本再做关键词匹配。

        Returns:
            ``{stock_code, stock_name, nodes, links, link_summary, generated_at}``；
            ``links`` 为 ``[[...]]`` 列表，``link_summary`` 为顿号分隔的链接串。
        """
        stock_code = str(metadata.get("stock_code") or metadata.get("code") or "unknown")
        stock_name = str(metadata.get("stock_name") or metadata.get("name") or "未知股票")
        nodes: List[Dict[str, str]] = [{"category": "stock", "name": f"{stock_code}-{stock_name}"}]

        industry = str(metadata.get("industry") or "").strip()
        if industry and industry != "待映射":
            nodes.append({"category": "industry", "name": industry})

        for concept in self._as_list(metadata.get("concepts")):
            nodes.append({"category": "concept", "name": concept})

        ma_state = str(quote_snapshot.get("ma_state") or "").strip()
        if ma_state and ma_state != "等待确认":
            nodes.append({"category": "technical", "name": ma_state})
        risk = str(quote_snapshot.get("risk") or "").strip()
        if risk and risk not in ("未知", "待确认"):
            nodes.append({"category": "risk", "name": f"{risk}风险"})
        if self._number(quote_snapshot.get("turnover_rate")) >= 20 or self._number(quote_snapshot.get("turnover_percentile")) >= 85:
            nodes.append({"category": "risk", "name": "高换手"})
        if self._number(quote_snapshot.get("distribution_score")) >= 70:
            nodes.append({"category": "risk", "name": "疑似派发"})

        text = "\n".join(str(value or "") for value in review_fields.values())
        for category, rules in self.RULES.items():
            for name, keywords in rules:
                if any(keyword in text for keyword in keywords):
                    nodes.append({"category": category, "name": name})

        unique_nodes = self._dedupe_nodes(nodes)
        links = [self._wikilink(node) for node in unique_nodes]
        return {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "nodes": unique_nodes,
            "links": links,
            "link_summary": "、".join(links),
            "generated_at": now_iso(),
        }

    def write_concept_notes(self, context: Dict[str, Any]) -> None:
        """把节点写成 Obsidian 笔记，并保证每篇都回链到个股笔记。

        已存在的笔记只在缺少个股链接时追加一行，不覆盖正文——用户可能已经在节点
        笔记里写了内容。新建笔记写入 frontmatter（``node_type`` 与
        ``knowledge-graph`` 标签）、说明和相关复盘三节。

        Args:
            context: ``build_review_context`` 的返回值；``stock`` 分类会被跳过，
                个股笔记由 ``ObsidianTradingService`` 维护，这里只补链接。

        Raises:
            OSError: 建目录、读旧文件或写文件失败；``UnicodeDecodeError`` 表示旧笔记
                不是 UTF-8。
        """
        stock_link = f"[[{context.get('stock_code')}-{context.get('stock_name')}]]"
        for node in context.get("nodes") or []:
            category = node.get("category")
            if category == "stock":
                continue
            name = str(node.get("name") or "").strip()
            if not name:
                continue
            folder = self.vault_root / "知识图谱" / self.CATEGORY_FOLDERS.get(category, category)
            folder.mkdir(parents=True, exist_ok=True)
            title = self._node_title(category, name)
            path = folder / f"{self._safe_filename(title)}.md"
            if path.exists():
                content = path.read_text(encoding="utf-8")
                if stock_link not in content:
                    content = content.rstrip() + f"\n- {stock_link}\n"
                    path.write_text(content, encoding="utf-8")
                continue
            path.write_text(
                (
                    "---\n"
                    f"title: {title}\n"
                    f"node_type: {category}\n"
                    "tags:\n"
                    "  - knowledge-graph\n"
                    f"  - knowledge-graph/{category}\n"
                    "---\n\n"
                    f"# {title}\n\n"
                    "## 说明\n\n"
                    "- 该节点由 python-a 复盘流程自动维护，用于把股票、板块、技术形态、风险和交易行为连接起来。\n\n"
                    "## 相关复盘\n\n"
                    f"- {stock_link}\n"
                ),
                encoding="utf-8",
            )

    def markdown_section(self, context: Dict[str, Any]) -> str:
        """生成要嵌入复盘笔记的“知识图谱链接”小节。

        Returns:
            以 ``####`` 开头的 Markdown 片段；``context`` 里没有链接时返回空串，
            调用方可以直接拼接，不会留下一个空标题。
        """
        if not context.get("links"):
            return ""
        lines = [
            "#### 知识图谱链接",
            "",
            f"- 关联节点：{context['link_summary']}",
            f"- 生成时间：{context.get('generated_at', '')}",
            "",
        ]
        return "\n".join(lines)

    def _wikilink(self, node: Dict[str, str]) -> str:
        """把节点转成 Obsidian 双链文本。

        个股用 ``代码-名称``（与个股笔记文件名一致），其余分类用
        ``_node_title`` 拼出的 ``分类-名称``，保证链接能解析到 ``write_concept_notes``
        写出的文件。
        """
        category = node.get("category") or ""
        name = node.get("name") or ""
        if category == "stock":
            return f"[[{name}]]"
        return f"[[{self._node_title(category, name)}]]"

    def _node_title(self, category: str, name: str) -> str:
        """拼出节点标题 ``{分类目录}-{名称}``。

        该标题会同时成为文件名与链接目标，两者必须一致；未登记的分类直接用
        ``category`` 原文当目录名，兼容后续新增分类。
        """
        folder = self.CATEGORY_FOLDERS.get(category, category)
        return f"{folder}-{name}"

    def _as_list(self, value: Any) -> List[str]:
        """把概念字段统一成去空白、去空项的字符串列表。

        兼容三种来源：已经是数组、英文逗号 / 中文逗号 / 斜杠 / 顿号分隔的字符串、
        以及空值。空值返回空列表而不是抛错，元数据缺失不应阻断复盘写入。
        """
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [item.strip() for item in re.split(r"[,，/、]", value) if item.strip()]
        return []

    def _dedupe_nodes(self, nodes: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
        """按 ``分类:名称`` 去重并丢弃空值，保持首次出现的顺序。

        key 用冒号拼接，只用于本次调用的去重集合；同时把节点重建为只含
        ``category`` / ``name`` 两个键的字典，丢掉调用方多传的字段。
        """
        seen: Set[str] = set()
        result: List[Dict[str, str]] = []
        for node in nodes:
            category = str(node.get("category") or "").strip()
            name = str(node.get("name") or "").strip()
            if not category or not name:
                continue
            key = f"{category}:{name}"
            if key in seen:
                continue
            seen.add(key)
            result.append({"category": category, "name": name})
        return result

    def _number(self, value: Any) -> float:
        """把阈值输入转成浮点数，无法解析时返回 0.0。

        返回 0 而不是抛错，是为了让“高换手 / 疑似派发”这类阈值规则在行情缺失时
        不触发；若改成抛错，一次快照缺字段就会让整篇复盘写不进去。
        """
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _safe_filename(self, value: str) -> str:
        """把节点标题转成 Windows 可用文件名。

        用 ``-`` 替换 Windows 文件名非法字符（尖括号、冒号、双引号、正斜杠、反斜杠、
        竖线、问号、星号）与 C0 控制字符（0x00–0x1f），再去掉首尾空白并截断到 120
        字符；结果为空时回退为“未命名”。截断上限是给概念名的路径长度留余量，并非
        文件系统硬限制。

        Args:
            value: 原始节点标题。

        Returns:
            可直接作为 ``.md`` 文件名主体的字符串，不含目录分隔符。
        """
        value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", value.strip())
        return value[:120] or "未命名"
