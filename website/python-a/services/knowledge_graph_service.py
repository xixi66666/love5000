from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set

from .storage_service import now_iso


class ObsidianKnowledgeGraphService:
    CATEGORY_FOLDERS = {
        "stock": "股票",
        "industry": "行业",
        "concept": "概念",
        "technical": "技术形态",
        "risk": "风险模式",
        "mistake": "交易错误",
        "plan": "观察计划",
    }

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
        self.vault_root = Path(vault_root)

    def build_review_context(
        self,
        metadata: Dict[str, Any],
        quote_snapshot: Dict[str, Any],
        review_fields: Dict[str, Any],
    ) -> Dict[str, Any]:
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
        category = node.get("category") or ""
        name = node.get("name") or ""
        if category == "stock":
            return f"[[{name}]]"
        return f"[[{self._node_title(category, name)}]]"

    def _node_title(self, category: str, name: str) -> str:
        folder = self.CATEGORY_FOLDERS.get(category, category)
        return f"{folder}-{name}"

    def _as_list(self, value: Any) -> List[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [item.strip() for item in re.split(r"[,，/、]", value) if item.strip()]
        return []

    def _dedupe_nodes(self, nodes: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
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
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _safe_filename(self, value: str) -> str:
        value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", value.strip())
        return value[:120] or "未命名"
