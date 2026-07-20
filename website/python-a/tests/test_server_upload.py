from io import BytesIO
from email.message import Message
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import server
from server import read_uploaded_image


class UploadImageTests(unittest.TestCase):
    def test_read_uploaded_image_extracts_file_and_trade_date(self):
        boundary = "----python-a-test"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="trade_date"\r\n\r\n'
            "2026-06-05\r\n"
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="account.jpg"\r\n'
            "Content-Type: image/jpeg\r\n\r\n"
        ).encode("utf-8") + b"\xff\xd8\xff\xd9" + f"\r\n--{boundary}--\r\n".encode("utf-8")
        headers = Message()
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        headers["Content-Length"] = str(len(body))
        handler = type("FakeHandler", (), {"headers": headers, "rfile": BytesIO(body)})()

        result = read_uploaded_image(handler)

        self.assertEqual(result["trade_date"], "2026-06-05")
        self.assertEqual(result["mime_type"], "image/jpeg")
        self.assertEqual(result["image_bytes"], b"\xff\xd8\xff\xd9")


class StockDailyReviewTests(unittest.TestCase):
    def test_write_stock_daily_review_adds_knowledge_graph_links_and_nodes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with mock.patch.object(server, "OBSIDIAN_ROOT", root), mock.patch.object(server, "DATA_ROOT", root / "data"):
                result = server.write_stock_daily_review(
                    {
                        "date": "2026-05-12",
                        "stock_code": "002580",
                        "stock_name": "圣阳股份",
                        "industry": "电池",
                        "quote_snapshot": {
                            "latest_price": 34.17,
                            "pct_change": -0.29,
                            "turnover_rate": 29.98,
                            "turnover_percentile": 96.4,
                            "distribution_score": 80,
                            "risk": "高",
                            "ma_state": "多头排列",
                        },
                        "technical_notes": "多头排列后出现高位震荡。",
                        "volume_notes": "高换手后收跌，疑似派发。",
                        "risk_notes": "不要追高，必须有止损条件。",
                        "plan_notes": "等待右侧确认，观察缩量回踩。",
                        "evaluation": "不追涨，等待风险释放。",
                    }
                )

                content = Path(result["daily_path"]).read_text(encoding="utf-8")
                self.assertIn("[[002580-圣阳股份]]", content)
                self.assertIn("[[行业-电池]]", content)
                self.assertIn("[[风险模式-高换手]]", content)
                self.assertTrue((root / "知识图谱" / "风险模式" / "风险模式-高换手.md").exists())


if __name__ == "__main__":
    unittest.main()
