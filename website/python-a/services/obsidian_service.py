from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from .storage_service import now_iso


class ObsidianTradingService:
    def __init__(self, vault_root: Path):
        self.vault_root = Path(vault_root)

    def ensure_dirs(self) -> None:
        for name in ["账户", "每日复盘", "股票"]:
            (self.vault_root / name).mkdir(parents=True, exist_ok=True)

    def write_daily_review(self, trade_date: str, snapshot: Dict[str, Any], trades: List[Dict[str, Any]], review: Dict[str, Any]) -> Dict[str, Any]:
        self.ensure_dirs()
        path = self.vault_root / "每日复盘" / f"{trade_date}-交易复盘.md"
        trade_lines = [
            f"- {item.get('stock_code', '')} {item.get('stock_name', '')} {item.get('side', '')} {item.get('price', '')} x {item.get('quantity', '')}"
            for item in trades
        ]
        markdown = (
            "---\n"
            f"title: {trade_date} 交易复盘\n"
            f"date: {trade_date}\n"
            "review_type: trading_daily_review\n"
            "tags:\n"
            "  - trading-review\n"
            "  - non-investment-advice\n"
            "---\n\n"
            f"# {trade_date} 交易复盘\n\n"
            "## 账户快照\n\n"
            f"- 总资产：{snapshot.get('total_assets', '--')}\n"
            f"- 本金：{snapshot.get('principal', '--')}\n"
            f"- 账户收益：{snapshot.get('account_profit', '--')}\n"
            f"- 当日参考盈亏：{snapshot.get('daily_profit', '--')}\n\n"
            "## 今日交易\n\n"
            f"{chr(10).join(trade_lines) if trade_lines else '- 今日无确认交易'}\n\n"
            "## 今日复盘\n\n"
            f"- 操作总结：{review.get('summary', '')}\n"
            f"- 做对了什么：{review.get('did_well', '')}\n"
            f"- 做错了什么：{review.get('mistake', '')}\n"
            f"- 仓位是否合理：{review.get('position_review', '')}\n"
            f"- 情绪是否影响操作：{review.get('emotion_review', '')}\n"
            f"- 明日观察计划：{review.get('next_plan', '')}\n"
            f"- 自由心得：{review.get('lesson', '')}\n\n"
            "> 本文只用于个人交易复盘和风险提示，非投资建议。\n"
        )
        path.write_text(markdown, encoding="utf-8")
        return {"ok": True, "success": True, "daily_review_path": str(path), "written_at": now_iso()}

    def update_stock_note(self, stock_code: str, stock_name: str, trades: List[Dict[str, Any]], review_links: List[str], ai_summary: str) -> Dict[str, Any]:
        self.ensure_dirs()
        path = self.vault_root / "股票" / f"{stock_code}-{stock_name}.md"
        manual_heading = "## 我的手写心得"
        manual_section = f"{manual_heading}\n\n"

        if path.exists():
            content = path.read_text(encoding="utf-8")
            if manual_heading in content:
                manual_section = content[content.index(manual_heading):].rstrip() + "\n"
        trade_lines = [
            f"- {item.get('trade_date', '')} {item.get('side', '')} {item.get('price', '')} x {item.get('quantity', '')}"
            for item in trades
        ]
        link_lines = [f"- [[{link}]]" for link in review_links]
        system_section = (
            f"# {stock_code} {stock_name}\n\n"
            "## 系统维护区\n\n"
            "### 交易统计\n\n"
            f"- 已记录交易数：{len(trades)}\n\n"
            "### 最近交易\n\n"
            f"{chr(10).join(trade_lines) if trade_lines else '- 暂无交易'}\n\n"
            "### 复盘索引\n\n"
            f"{chr(10).join(link_lines) if link_lines else '- 暂无复盘'}\n\n"
            "### AI 个股经验摘要\n\n"
            f"{ai_summary or '暂无摘要'}\n\n"
            "### 后续观察计划\n\n"
            "- 等待下一次确认复盘后更新。\n\n"
        )
        path.write_text(system_section + manual_section, encoding="utf-8")
        return {"ok": True, "success": True, "stock_path": str(path), "written_at": now_iso()}

    def update_insight_index(self, insight: Dict[str, Any]) -> Dict[str, Any]:
        self.vault_root.mkdir(parents=True, exist_ok=True)
        path = self.vault_root / "交易心得总纲.md"
        markdown = (
            "# 交易心得总纲\n\n"
            "## 最近更新摘要\n\n"
            f"{insight.get('summary', '')}\n\n"
            "## 高频错误模式\n\n"
            f"{self._bullet_list(insight.get('mistakes'))}\n\n"
            "## 有效操作模式\n\n"
            f"{self._bullet_list(insight.get('effective_patterns'))}\n\n"
            "## 情绪和纪律问题\n\n"
            f"{self._bullet_list(insight.get('discipline'))}\n\n"
            "## 仓位管理教训\n\n"
            f"{self._bullet_list(insight.get('position_lessons'))}\n\n"
            "## 买入前检查清单\n\n"
            f"{self._bullet_list(insight.get('buy_checklist'))}\n\n"
            "## 卖出前检查清单\n\n"
            f"{self._bullet_list(insight.get('sell_checklist'))}\n\n"
            "## 仍待验证的策略假设\n\n"
            f"{self._bullet_list(insight.get('hypotheses'))}\n\n"
            "> 本文件只用于个人复盘，非投资建议。\n"
        )
        path.write_text(markdown, encoding="utf-8")
        return {"ok": True, "success": True, "insight_path": str(path), "written_at": now_iso()}

    def _bullet_list(self, values: Any) -> str:
        if not isinstance(values, list) or not values:
            return "- 暂无"
        return "\n".join(f"- {value}" for value in values)
