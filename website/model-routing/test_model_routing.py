"""``model_routing`` 的单元测试。

覆盖：统一入口请求只打固定服务路径且不带 ``Authorization``；已选模型时网关离线不回退；
``try_chat`` 只接受 200/204；超时、HTTP 错误、非法 JSON 一律抛错；原配置直连保留鉴权但
错误只暴露状态码；异步通道与同步共用同一套地址校验；部署副本与公共源码逐字节一致。

``model_routing`` 通过 ``importlib`` 从文件加载（目录名带连字符，无法当包导入），
``_open``/``_state_path`` 用 mock 替换，不启动 website、不联网。
"""

import asyncio
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

spec = importlib.util.spec_from_file_location("routing", Path(__file__).with_name("model_routing.py"))
routing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(routing)


class ModelRoutingTests(unittest.TestCase):
    """``ModelRoutingTests`` 覆盖的分支。

    - 统一入口：请求路径、方法、自定义头与“不携带提供方密钥”；
    - 离线判定：已选模型直接报错、显式 ``native`` 允许回退、状态文件损坏按已选处理；
    - 生成：``try_chat`` 的 200/204 语义，以及超时/HTTP 错误/非法 JSON 一律不回退；
    - 原配置直连：鉴权头与请求体保留、错误信息脱敏、异步客户端参数；
    - 打包：三个部署副本与公共源码逐字节一致，副本可独立运行。
    """
    def test_actual_request_uses_fixed_service_and_never_sends_original_key(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"model":"selected"}'
        with patch.object(routing, "_open", return_value=response) as open_url:
            self.assertEqual(routing.chat("python-a", {"messages": [{"content": "hello"}]}), {"model": "selected"})
            req = open_url.call_args[0][0]
            self.assertTrue(req.full_url.endswith("/api/models/chat/python-a"))
            self.assertNotIn("Authorization", req.headers)

    def test_selected_gateway_offline_does_not_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / "state.json"
            state.write_text(json.dumps({"global": "deepseek:pro", "skill-finder": "native"}))
            with patch.object(routing, "_state_path", lambda: state), patch.object(routing, "_call", side_effect=URLError(ConnectionRefusedError())):
                with self.assertRaisesRegex(routing.ModelRoutingError, "离线"):
                    routing.active("python-a")
                self.assertFalse(routing.active("skill-finder"))

    def test_complete_uses_one_post_and_accepts_only_explicit_native_response(self):
        response = MagicMock()
        response.__enter__.return_value.status = 200
        response.__enter__.return_value.read.return_value = b'{"model":"selected"}'
        with patch.object(routing, "_open", return_value=response) as open_url:
            self.assertEqual(routing.try_chat("python-a", {"messages": []})["model"], "selected")
            open_url.assert_called_once()
            req = open_url.call_args[0][0]
            self.assertEqual(req.get_method(), "POST")
            self.assertTrue(req.full_url.endswith("/api/models/complete/python-a"))
            self.assertNotIn("Authorization", req.headers)
            response.__enter__.return_value.status = 204
            self.assertIsNone(routing.try_chat("python-a", {}))

    def test_failed_post_never_falls_back_after_timeout_http_error_or_invalid_json(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / "state.json"
            state.write_text('{"global":"native"}')
            for failure in (TimeoutError(), URLError(TimeoutError()),
                            HTTPError("http://127.0.0.1", 502, "private detail", {}, None)):
                with self.subTest(failure=type(failure)), patch.object(routing, "_state_path", lambda: state), patch.object(routing, "_open", side_effect=failure), self.assertRaises(routing.ModelRoutingError):
                    routing.try_chat("python-a", {})
            response = MagicMock()
            response.__enter__.return_value.status = 200
            response.__enter__.return_value.read.return_value = b'null'
            with patch.object(routing, "_open", return_value=response), self.assertRaises(routing.ModelRoutingError):
                routing.try_chat("python-a", {})

    def test_connection_refused_respects_persisted_global_override_and_corrupt_state(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / "state.json"
            with patch.object(routing, "_state_path", lambda: state), patch.object(routing, "_open", side_effect=URLError(ConnectionRefusedError())):
                state.write_text('{"global":"mimo:pro","skill-finder":"native"}')
                with self.assertRaises(routing.ModelRoutingError):
                    routing.try_chat("python-a", {})
                self.assertIsNone(routing.try_chat("skill-finder", {}))
                state.write_text('[]')
                with self.assertRaises(routing.ModelRoutingError):
                    routing.try_chat("skill-finder", {})

    def test_native_transport_preserves_auth_payload_and_sanitizes_provider_error(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"choices":[]}'
        with patch.object(routing, "_open", return_value=response) as open_url:
            routing.native_chat("https://provider.example/chat/completions", "test-key", {"model": "native"})
            req = open_url.call_args[0][0]
            self.assertEqual(req.headers["Authorization"], "Bearer test-key")
            self.assertEqual(json.loads(req.data)["model"], "native")
        failure = HTTPError("https://provider.example", 401, "secret response", {}, None)
        with patch.object(routing, "_open", side_effect=failure), self.assertRaises(routing.ModelProviderError) as caught:
            routing.native_chat("https://provider.example/chat/completions", "test-key", {})
        self.assertEqual(caught.exception.status, 401)
        self.assertNotIn("secret", str(caught.exception))

    def test_async_native_transport_shares_headers_validation_and_sanitized_status(self):
        class Client:
            async def post(self, url, **kwargs):
                self.kwargs = kwargs
                return self.response
        client = Client()
        client.response = MagicMock(status_code=200, content=b'{"model":"native"}')
        result = asyncio.run(routing.native_chat_async(
            client, "https://provider.example/chat/completions", "test-key", {},
            headers={"x-opencode-session": "test-session"}))
        self.assertEqual(result["model"], "native")
        self.assertEqual(client.kwargs["headers"]["Authorization"], "Bearer test-key")
        self.assertEqual(client.kwargs["headers"]["x-opencode-session"], "test-session")
        self.assertFalse(client.kwargs["follow_redirects"])
        client.response = MagicMock(status_code=401, content=b'private detail')
        with self.assertRaises(routing.ModelProviderError) as caught:
            asyncio.run(routing.native_chat_async(client, "https://provider.example/chat/completions", "test-key", {}))
        self.assertEqual(caught.exception.status, 401)
        self.assertNotIn("private", str(caught.exception))

    def test_packaged_client_is_synchronized_and_works_without_repository(self):
        root = Path(__file__).resolve().parents[2]
        source = Path(routing.__file__).read_bytes()
        properties_source = Path(__file__).with_name("model_properties.py").read_bytes()
        for relative in ("website/python-a/services/_model_routing.py",
                         "website/scrapling-ui/backend/services/_model_routing.py",
                         "website/skill-finder/backend/app/services/_model_routing.py"):
            self.assertEqual((root / relative).read_bytes(), source,
                             "Run python scripts/sync-model-routing.py")
        for relative in ("website/python-a/services/_model_properties.py",
                         "website/scrapling-ui/backend/services/_model_properties.py",
                         "website/skill-finder/backend/app/services/_model_properties.py"):
            self.assertEqual((root / relative).read_bytes(), properties_source,
                             "Run python scripts/sync-model-routing.py")
        with tempfile.TemporaryDirectory() as folder:
            copy = Path(folder) / "standalone.py"
            copy.write_bytes(source)
            standalone_spec = importlib.util.spec_from_file_location("standalone_routing", copy)
            standalone = importlib.util.module_from_spec(standalone_spec)
            standalone_spec.loader.exec_module(standalone)
            with patch.object(standalone, "_state_path", lambda: Path(folder) / "missing.json"), patch.object(standalone, "_open", side_effect=URLError(ConnectionRefusedError())):
                self.assertIsNone(standalone.try_chat("skill-finder", {}))


if __name__ == "__main__":
    unittest.main()
