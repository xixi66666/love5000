"""server 模块里“截图上传解析”与“个股日复盘写盘”两条链路的单元测试。

被测对象：``server.read_uploaded_image`` 的 multipart 解析（含 trade_date 字段与文件字节），
以及 ``server.write_stock_daily_review`` 生成的知识图谱双链、研究数据快照与节点文件。

隔离：上传用例用 ``BytesIO`` 冒充 rfile、用 ``email.message.Message`` 冒充请求头，不监听端口；
复盘用例把 ``server.OBSIDIAN_ROOT`` / ``server.DATA_ROOT`` / ``server.StockMetadataService``
全部 mock 到临时目录和替身上，不触碰真实 vault、不请求行情或元数据接口。
"""
from io import BytesIO
from email.message import Message
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import server
from server import read_uploaded_image


class UploadImageTests(unittest.TestCase):
    """覆盖 multipart 解析：文本字段 trade_date、文件 MIME 类型与文件字节都要正确取出。"""
    def test_read_uploaded_image_extracts_file_and_trade_date(self):
        # server 自己解析 multipart，因此这里手工拼一段等价报文：一个文本字段加一个文件字段。
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
    """覆盖个股日复盘的完整落盘：知识图谱双链、研究快照正文、券商展示名与风险节点文件。"""
    def test_write_stock_daily_review_adds_knowledge_graph_links_and_nodes(self):
        class FakeMetadataService:
            """返回固定行业与概念的元数据替身，避免复盘用例依赖真实板块接口。"""
            def __init__(self, data_root):
                self.data_root = data_root

            def get_stock_metadata(self, code, fallback=None):
                fallback = fallback or {}
                return {
                    "code": code,
                    "name": fallback.get("name", "圣阳股份"),
                    "industry": fallback.get("industry", "电池"),
                    "board": fallback.get("board", "A股"),
                    "concepts": fallback.get("concepts", []),
                    "source": "test",
                }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with mock.patch.object(server, "OBSIDIAN_ROOT", root), mock.patch.object(
                server, "DATA_ROOT", root / "data"
            ), mock.patch.object(server, "StockMetadataService", FakeMetadataService):
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
                        "research_snapshot": {
                            "code": "002580",
                            "overview": {
                                "valuation": {
                                    "success": True,
                                    "provider": "tencent",
                                    "data_date": "2026-07-13",
                                    "pe_ttm": 26.8,
                                    "pb": 2.35,
                                }
                            },
                            "capital": {
                                "fund_flow": {
                                    "success": True,
                                    "provider": "sina",
                                    "data_date": "2026-07-11",
                                    "five_day_direction": "净流入",
                                }
                            },
                            "events": {
                                "reports": {
                                    "success": True,
                                    "provider": "eastmoney",
                                    "data_date": "2026-07-10",
                                    "items": [{"title": "储能业务跟踪"}],
                                }
                            },
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
                self.assertIn("#### 研究数据快照", content)
                self.assertIn("PE(TTM)：26.8", content)
                self.assertIn("腾讯财经", content)
                self.assertIn("新浪财经", content)
                self.assertIn("储能业务跟踪", content)
                self.assertTrue((root / "知识图谱" / "风险模式" / "风险模式-高换手.md").exists())


if __name__ == "__main__":
    unittest.main()
