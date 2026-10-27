import json
import unittest
from unittest.mock import patch

import server
from services import model_hub


class ModelIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.payload = {"stock": {}, "research_snapshot": {"source": "test"}}
        self.result = {"model": "selected", "choices": [{"message": {
            "content": json.dumps({"research_conclusion": "test"})}}]}

    def test_selected_model_uses_one_hub_call_without_native_key(self):
        with patch.object(model_hub, "try_chat", return_value=self.result) as hub, patch.object(
                model_hub, "native_chat") as native, patch.object(server, "read_local_secret") as key:
            result = server.call_deepseek_dimension_analysis(self.payload)
            self.assertEqual(result["model"], "selected")
            hub.assert_called_once()
            key.assert_not_called()
            native.assert_not_called()

    def test_native_configuration_uses_shared_transport(self):
        with patch.object(model_hub, "try_chat", return_value=None), patch.object(
                model_hub, "native_chat", return_value=self.result) as native, patch.object(
                    server, "read_local_secret", return_value="test-key"):
            server.call_deepseek_dimension_analysis(self.payload)
            native.assert_called_once()
            self.assertEqual(native.call_args[0][1], "test-key")
            self.assertIn("messages", native.call_args[0][2])

    def test_gateway_failure_never_reads_native_key_or_calls_provider(self):
        with patch.object(model_hub, "try_chat", side_effect=RuntimeError("gateway unavailable")), patch.object(
                model_hub, "native_chat") as native, patch.object(server, "read_local_secret") as key:
            with self.assertRaises(RuntimeError):
                server.call_deepseek_dimension_analysis(self.payload)
            native.assert_not_called()
            key.assert_not_called()
