import tempfile
import unittest
from pathlib import Path

from services.knowledge_graph_service import ObsidianKnowledgeGraphService


class ObsidianKnowledgeGraphServiceTests(unittest.TestCase):
    def test_build_review_context_links_metadata_and_detected_patterns(self):
        service = ObsidianKnowledgeGraphService(Path("unused"))

        context = service.build_review_context(
            {
                "stock_code": "002580",
                "stock_name": "圣阳股份",
                "industry": "电池",
                "concepts": ["储能", "钠离子电池"],
            },
            {
                "ma_state": "多头排列",
                "risk": "高",
                "turnover_rate": 29.98,
                "turnover_percentile": 96.4,
                "distribution_score": 80,
            },
            {
                "technical_notes": "均线多头排列，但高位震荡。",
                "volume_notes": "高换手后收跌，疑似派发。",
                "risk_notes": "主要风险是追高和没有止损条件。",
                "plan_notes": "明日等待右侧确认，观察缩量回踩。",
                "evaluation": "不追涨，等待风险释放。",
            },
        )

        self.assertIn("[[002580-圣阳股份]]", context["link_summary"])
        self.assertIn("[[行业-电池]]", context["link_summary"])
        self.assertIn("[[概念-储能]]", context["link_summary"])
        self.assertIn("[[技术形态-多头排列]]", context["link_summary"])
        self.assertIn("[[风险模式-高换手]]", context["link_summary"])
        self.assertIn("[[交易错误-追高]]", context["link_summary"])
        self.assertIn("[[观察计划-等待右侧确认]]", context["link_summary"])

    def test_write_concept_notes_creates_readable_markdown_nodes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = ObsidianKnowledgeGraphService(root)
            context = service.build_review_context(
                {"stock_code": "002580", "stock_name": "圣阳股份", "industry": "电池", "concepts": ["储能"]},
                {"ma_state": "多头排列", "turnover_percentile": 95},
                {"risk_notes": "高换手，疑似派发。", "plan_notes": "等待右侧确认。"},
            )

            service.write_concept_notes(context)

            industry_note = root / "知识图谱" / "行业" / "行业-电池.md"
            risk_note = root / "知识图谱" / "风险模式" / "风险模式-高换手.md"
            self.assertTrue(industry_note.exists())
            self.assertTrue(risk_note.exists())
            self.assertIn("相关复盘", industry_note.read_text(encoding="utf-8"))
            self.assertIn("[[002580-圣阳股份]]", risk_note.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
