"""Obsidian 交易笔记服务（services.obsidian_service.ObsidianTradingService）的单元测试。

被测对象：日复盘 Markdown 的生成、股票笔记“系统维护区 + 手写心得区”的合并，以及洞察索引的
分节写入；三者都直接决定写进用户真实 vault 的内容，因此断言的是正文关键字而不是文件存在。

隔离：每个用例用 ``tempfile.TemporaryDirectory`` 充当 vault 根，所有路径都落在临时目录内，
不读写 obsidian-vault/A股AI，也不发网络请求。
"""
import tempfile
import unittest
from pathlib import Path

from services.obsidian_service import ObsidianTradingService


class ObsidianTradingServiceTests(unittest.TestCase):
    """覆盖三个写入入口：日复盘文件、股票笔记保留手写区、洞察索引分节。"""
    def test_write_daily_review_creates_markdown_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = ObsidianTradingService(Path(temp_dir))

            result = service.write_daily_review(
                "2026-06-05",
                {"total_assets": 15909.86, "account_profit": -90.14},
                [{"stock_code": "601991", "stock_name": "大唐发电", "side": "buy", "price": 8.99, "quantity": 300}],
                {"summary": "今天冲动买入。", "lesson": "先写计划再下单。"},
            )

            path = Path(result["daily_review_path"])
            content = path.read_text(encoding="utf-8")
            self.assertIn("# 2026-06-05 交易复盘", content)
            self.assertIn("大唐发电", content)
            self.assertIn("非投资建议", content)

    def test_update_stock_note_preserves_manual_section(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            stock_file = root / "股票" / "601991-大唐发电.md"
            stock_file.parent.mkdir(parents=True)
            stock_file.write_text(
                "# 601991 大唐发电\n\n## 系统维护区\n\n旧内容\n\n## 我的手写心得\n\n这里别覆盖。\n",
                encoding="utf-8",
            )
            service = ObsidianTradingService(root)

            service.update_stock_note(
                "601991",
                "大唐发电",
                [{"trade_date": "2026-06-05", "side": "buy", "price": 8.99, "quantity": 300}],
                ["2026-06-05-交易复盘.md"],
                "这只股票容易追高，需要等待计划内位置。",
            )

            content = stock_file.read_text(encoding="utf-8")
            self.assertIn("这只股票容易追高", content)
            self.assertIn("这里别覆盖。", content)

    def test_update_insight_index_writes_sections(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = ObsidianTradingService(Path(temp_dir))

            result = service.update_insight_index(
                {
                    "summary": "本周最大问题是仓位太满。",
                    "mistakes": ["追高", "没写卖出条件"],
                    "effective_patterns": ["分批买入"],
                    "discipline": ["下单前截图复核"],
                    "position_lessons": ["单票仓位不要超过计划"],
                    "buy_checklist": ["板块是否共振"],
                    "sell_checklist": ["跌破条件是否触发"],
                    "hypotheses": ["电力板块持续性需要成交额验证"],
                }
            )

            content = Path(result["insight_path"]).read_text(encoding="utf-8")
            self.assertIn("## 高频错误模式", content)
            self.assertIn("追高", content)


if __name__ == "__main__":
    unittest.main()
