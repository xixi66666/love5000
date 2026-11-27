"""交易复盘与交易心得写入 Obsidian Markdown 的服务。

对外提供 ``ObsidianTradingService``：``ensure_dirs`` 预建目录，
``write_daily_review`` 写每日复盘，``update_stock_note`` 维护个股笔记，
``update_insight_index`` 写交易心得总纲。

磁盘布局（``vault_root`` 生产为 ``obsidian-vault/A股AI``）：

- ``账户/``：``ensure_dirs`` 预建，留给账户类笔记。
- ``每日复盘/{YYYY-MM-DD}-交易复盘.md``：整文件覆盖，含 frontmatter
  （``review_type: trading_daily_review``、``non-investment-advice`` 标签）、
  账户快照、今日交易与复盘正文。
- ``股票/{代码}-{名称}.md``：上半部分为系统维护区（交易统计、最近交易、复盘索引、
  AI 摘要、后续观察计划），下半部分原样保留 ``## 我的手写心得`` 之后的手写内容。
- ``交易心得总纲.md``：模型归纳的错误模式、有效模式、纪律问题、仓位教训与买卖前
  检查清单。

数据来源：快照与成交来自 ``AccountService`` / ``TradeService``，复盘正文与心得来自
统一模型输出。降级策略：本层不捕获 I/O 异常，由 ``server.py`` 转成 ``success=false``；
每篇笔记都是整文件覆盖而不是追加，所以同一交易日重复提交以最后一次为准。文件名直接
拼接股票代码与名称，调用方需保证名称里没有路径分隔符。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from .storage_service import now_iso


class ObsidianTradingService:
    """把交易数据渲染成 Obsidian 笔记并写入 Vault。

    实例只保存 Vault 根目录，本身无状态；渲染全部用字符串模板完成，不依赖第三方
    Markdown 库，也不访问网络。
    """

    def __init__(self, vault_root: Path):
        """绑定 Vault 根目录。

        Args:
            vault_root: Obsidian Vault 内的写入根目录（生产为
                ``obsidian-vault/A股AI``），接受 ``str`` 或 ``Path``，内部统一成 ``Path``。
        """
        self.vault_root = Path(vault_root)

    def ensure_dirs(self) -> None:
        """创建“账户 / 每日复盘 / 股票”三个固定子目录。

        ``exist_ok=True`` 使其幂等：``write_daily_review`` 与 ``update_stock_note``
        开头都会调用，重复建目录不会报错，也不会等到首次写入才暴露父目录不存在。
        写“交易心得总纲”的 ``update_insight_index`` 只保证 Vault 根目录存在。
        """
        for name in ["账户", "每日复盘", "股票"]:
            (self.vault_root / name).mkdir(parents=True, exist_ok=True)

    def write_daily_review(self, trade_date: str, snapshot: Dict[str, Any], trades: List[Dict[str, Any]], review: Dict[str, Any]) -> Dict[str, Any]:
        """写入（覆盖）某交易日的复盘笔记。

        Args:
            trade_date: 交易日 ``YYYY-MM-DD``，同时用作文件名与 frontmatter 的
                ``title`` / ``date``。
            snapshot: 账户快照行。缺失字段渲染成 ``--`` 而不是 0，避免把“没取到”
                显示成“资产为零”。
            trades: 当日已确认成交，逐行渲染为“代码 名称 方向 价格 x 数量”；
                为空时写“今日无确认交易”。
            review: 复盘字段（summary / did_well / mistake / position_review /
                emotion_review / next_plan / lesson），缺失字段渲染为空串。

        Returns:
            ``{ok, success, daily_review_path, written_at}``，路径为绝对路径，
            便于页面直接显示或提供打开。

        Raises:
            OSError: 创建目录或写文件失败，例如 Vault 目录被其他程序占用。

        正文里的多行列表用 ``chr(10)`` 拼接，而不是在 f-string 的表达式部分写反斜杠
        转义：项目基线是 Python 3.9，3.12 之前的 f-string 表达式里不允许出现反斜杠。
        """
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
        """重建个股笔记的系统维护区，并保留用户手写心得。

        文件已存在且包含 ``## 我的手写心得`` 时，把该标题及之后的内容原样截取并追加
        到新正文末尾；没有该标题或文件不存在时只写系统维护区。这样自动复盘不会覆盖
        用户在 Obsidian 里手写的复盘。

        Args:
            stock_code: 6 位代码，直接进入文件名 ``{代码}-{名称}.md``。
            stock_name: 股票名称，直接进入文件名。
            trades: 该股票的历史成交，用于渲染交易条数与最近交易列表（不截断）。
            review_links: 复盘笔记的链接目标（不含双方括号），逐条渲染成双链。
            ai_summary: 模型归纳的个股经验摘要，为空时写“暂无摘要”。

        Returns:
            ``{ok, success, stock_path, written_at}``。

        Raises:
            OSError: 读写失败。
            UnicodeDecodeError: 旧文件不是 UTF-8（例如在别的编辑器里另存为 GBK）。
        """
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
        """用最新一次模型归纳整体覆盖“交易心得总纲”。

        总纲是可再生成的汇总，因此每次整文件重写；段落固定为最近摘要、高频错误、
        有效操作、情绪纪律、仓位教训、买卖前检查清单与待验证假设。``summary`` 缺失时
        该段留空，列表型字段缺失时由 ``_bullet_list`` 写成“- 暂无”，不会出现空标题。

        Args:
            insight: 模型输出的心得字典，键见上段；非列表值按空处理。

        Returns:
            ``{ok, success, insight_path, written_at}``。

        Raises:
            OSError: 创建根目录或写文件失败。
        """
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
        """把模型返回的列表渲染成 Markdown 无序列表。

        只接受 ``list``：上游给字符串、数字或空值时统一退化为“- 暂无”，避免把
        JSON 片段或裸字符串原样贴进笔记。

        Returns:
            每项一行 ``- 内容``；非列表或空列表返回 ``- 暂无``。
        """
        if not isinstance(values, list) or not values:
            return "- 暂无"
        return "\n".join(f"- {value}" for value in values)
