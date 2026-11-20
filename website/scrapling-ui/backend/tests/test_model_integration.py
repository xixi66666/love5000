import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from services import deepseek_healer as healer


class _Route:
    model_id = "deepseek-v4-pro"
    provider = SimpleNamespace(api_key="test-key", base_url="https://api.example/v1")


class _Settings:
    def route(self, scope):
        return _Route()


class ModelIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.page = AsyncMock()
        self.page.evaluate.return_value = "<button id='fixed'>Test</button>"
        self.result = {"choices": [{"message": {"content": "```css\n#fixed\n```"}}]}
        self.patch = patch.object(
            healer.model_properties.ModelProperties, "load", classmethod(lambda cls: _Settings()))
        self.patch.start()
        self.addCleanup(self.patch.stop)

    async def test_selected_model_repairs_without_creating_native_client(self):
        with patch.object(healer.model_hub, "try_chat", AsyncMock(return_value=self.result)) as hub, patch.object(
                healer.httpx, "AsyncClient") as client:
            self.assertEqual(await healer.heal_selector("#broken", "click", self.page), "#fixed")
            hub.assert_awaited_once()
            client.assert_not_called()

    async def test_native_uses_shared_transport_and_model_properties_key(self):
        with patch.object(healer.model_hub, "try_chat", AsyncMock(return_value=None)), patch.object(
                healer.model_hub, "native_chat", AsyncMock(return_value=self.result)) as native:
            self.assertEqual(await healer.heal_selector("#broken", "click", self.page), "#fixed")
            native.assert_awaited_once()
            self.assertEqual(native.call_args.args[1], "https://api.example/v1/chat/completions")
            self.assertEqual(native.call_args.args[2], "test-key")
            self.assertEqual(native.call_args.args[3]["model"], "deepseek-v4-pro")

    async def test_failed_selected_model_never_calls_native(self):
        with patch.object(healer.model_hub, "try_chat", AsyncMock(side_effect=RuntimeError("private detail"))), patch.object(
                healer.model_hub, "native_chat", AsyncMock()) as native:
            with self.assertRaisesRegex(RuntimeError, "统一模型"):
                await healer.heal_selector("#broken", "click", self.page)
            native.assert_not_awaited()
