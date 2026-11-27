"""维度分析调用与统一模型路由（server.call_deepseek_dimension_analysis）的接线测试。

被测对象：server 在“已选择统一模型”“回退服务原配置”“模型网关异常”三种情况下的调用路径，
重点是不可越权：统一模型分支不得读取原生密钥，网关报错也不得偷偷回退到服务原配置。

隔离：用 ``unittest.mock.patch`` 替身替换 ``server.text_route`` 与 ``model_hub.try_chat`` /
``model_hub.native_chat``，既不读取 model.properties，也不发起任何真实 HTTP 请求；
路由对象由 ``types.SimpleNamespace`` 手工构造。
"""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import server
from services import model_hub


class ModelIntegrationTests(unittest.TestCase):
    """覆盖三条分支：统一模型优先、原配置共用公共 transport、网关异常时绝不回退原生密钥。"""
    def setUp(self):
        self.payload = {"stock": {}, "research_snapshot": {"source": "test"}}
        self.result = {"model": "selected", "choices": [{"message": {
            "content": json.dumps({"research_conclusion": "test"})}}]}
        self.route = SimpleNamespace(
            model_id="deepseek-v4-pro",
            provider=SimpleNamespace(api_key="test-key", base_url="https://api.example/v1"))

    def test_selected_model_uses_one_hub_call_without_native_key(self):
        with patch.object(server, "text_route", return_value=self.route) as route, patch.object(
                model_hub, "try_chat", return_value=self.result) as hub, patch.object(
                model_hub, "native_chat") as native:
            result = server.call_deepseek_dimension_analysis(self.payload)
            self.assertEqual(result["model"], "selected")
            hub.assert_called_once()
            self.assertEqual(hub.call_args.args[0]["model"], "deepseek-v4-pro")
            route.assert_called_once()
            native.assert_not_called()

    def test_native_configuration_uses_shared_transport(self):
        with patch.object(server, "text_route", return_value=self.route), patch.object(
                model_hub, "try_chat", return_value=None), patch.object(
                model_hub, "native_chat", return_value=self.result) as native:
            server.call_deepseek_dimension_analysis(self.payload)
            native.assert_called_once()
            self.assertEqual(native.call_args.args[0], "https://api.example/v1/chat/completions")
            self.assertEqual(native.call_args.args[1], "test-key")
            self.assertIn("messages", native.call_args.args[2])

    def test_gateway_failure_never_reads_native_key_or_calls_provider(self):
        with patch.object(server, "text_route", return_value=self.route), patch.object(
                model_hub, "try_chat", side_effect=RuntimeError("gateway unavailable")), patch.object(
                model_hub, "native_chat") as native:
            with self.assertRaises(RuntimeError):
                server.call_deepseek_dimension_analysis(self.payload)
            native.assert_not_called()
