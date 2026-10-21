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
            with patch.dict(routing.os.environ, {"MODEL_ROUTING_STATE": str(state)}), patch.object(routing, "_call", side_effect=URLError(ConnectionRefusedError())):
                with self.assertRaisesRegex(routing.ModelRoutingError, "离线"):
                    routing.active("python-a")
                self.assertFalse(routing.active("skill-finder"))

    def test_unknown_remote_hub_is_rejected(self):
        with patch.dict(routing.os.environ, {"MODEL_HUB_URL": "https://evil.example"}), self.assertRaises(routing.ModelRoutingError):
            routing._hub()

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
                with self.subTest(failure=type(failure)), patch.dict(routing.os.environ, {"MODEL_ROUTING_STATE": str(state)}), patch.object(routing, "_open", side_effect=failure), self.assertRaises(routing.ModelRoutingError):
                    routing.try_chat("python-a", {})
            response = MagicMock()
            response.__enter__.return_value.status = 200
            response.__enter__.return_value.read.return_value = b'null'
            with patch.object(routing, "_open", return_value=response), self.assertRaises(routing.ModelRoutingError):
                routing.try_chat("python-a", {})

    def test_connection_refused_respects_persisted_global_override_and_corrupt_state(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / "state.json"
            with patch.dict(routing.os.environ, {"MODEL_ROUTING_STATE": str(state)}), patch.object(routing, "_open", side_effect=URLError(ConnectionRefusedError())):
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
        for relative in ("website/python-a/services/_model_routing.py",
                         "website/scrapling-ui/backend/services/_model_routing.py",
                         "website/skill-finder/backend/app/services/_model_routing.py"):
            self.assertEqual((root / relative).read_bytes(), source,
                             "Run python scripts/sync-model-routing.py")
        with tempfile.TemporaryDirectory() as folder:
            copy = Path(folder) / "standalone.py"
            copy.write_bytes(source)
            standalone_spec = importlib.util.spec_from_file_location("standalone_routing", copy)
            standalone = importlib.util.module_from_spec(standalone_spec)
            standalone_spec.loader.exec_module(standalone)
            with patch.dict(standalone.os.environ, {"MODEL_ROUTING_STATE": str(Path(folder) / "missing.json")}), patch.object(standalone, "_open", side_effect=URLError(ConnectionRefusedError())):
                self.assertIsNone(standalone.try_chat("skill-finder", {}))


if __name__ == "__main__":
    unittest.main()
