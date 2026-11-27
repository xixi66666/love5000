"""选择器修复（``heal_selector``）的模型路由分支测试。

覆盖三条分支：

- 统一模型入口可用：走 ``model_hub.try_chat``，不能另外新建 httpx 原生客户端。
- 统一入口返回 ``None``：回退到服务原配置，用共享传输函数 ``native_chat``，
  并校验 ``model.properties`` 里的 base_url/api-key/模型 id 被正确传入。
- 统一入口抛错：直接向上抛，异常信息里只有面向用户的提示，不泄露上游细节，
  更不会继续打原配置接口。

隔离手段：``page`` 是 ``AsyncMock``（页面 HTML 固定返回一段桩）；
``ModelProperties.load`` 被替换成只返回测试路由的桩类；``try_chat``/``native_chat``
全部 mock，不发任何真实 HTTP 请求，也不需要 ``model.properties`` 存在。
"""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from services import deepseek_healer as healer


class _Route:
    """`model_properties` 路由桩：一个固定模型 id 加一个带密钥的 provider。"""

    model_id = "deepseek-v4-pro"
    provider = SimpleNamespace(api_key="test-key", base_url="https://api.example/v1")


class _Settings:
    """`ModelProperties.load()` 的返回值替身，``route`` 不看 scope 一律给桩路由。"""

    def route(self, scope):
        return _Route()


class ModelIntegrationTests(unittest.IsolatedAsyncioTestCase):
    """三者共用的清理逻辑：patch 路由配置，保证每个用例都拿到同一套桩数据。"""

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
