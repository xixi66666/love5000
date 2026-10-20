import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import URLError

spec = importlib.util.spec_from_file_location("routing", Path(__file__).with_name("model_routing.py"))
routing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(routing)


class ModelRoutingTests(unittest.TestCase):
    def test_actual_request_uses_fixed_service_and_never_sends_original_key(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"model":"selected"}'
        with patch.object(routing.request, "urlopen", return_value=response) as open_url:
            self.assertEqual(routing.chat("python-a", {"messages": [{"content": "hello"}]}), {"model": "selected"})
            req = open_url.call_args[0][0]
            self.assertTrue(req.full_url.endswith("/api/models/chat/python-a"))
            self.assertNotIn("Authorization", req.headers)

    def test_selected_gateway_offline_does_not_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / "state.json"
            state.write_text(json.dumps({"global": "deepseek:pro", "skill-finder": "native"}))
            with patch.dict(routing.os.environ, {"MODEL_ROUTING_STATE": str(state)}), patch.object(routing, "_call", side_effect=URLError("offline")):
                with self.assertRaisesRegex(routing.ModelRoutingError, "离线"):
                    routing.active("python-a")
                self.assertFalse(routing.active("skill-finder"))

    def test_unknown_remote_hub_is_rejected(self):
        with patch.dict(routing.os.environ, {"MODEL_HUB_URL": "https://evil.example"}), self.assertRaises(routing.ModelRoutingError):
            routing._hub()


if __name__ == "__main__":
    unittest.main()
