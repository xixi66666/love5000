"""``model_properties`` 的单元测试。

覆盖：正常配置的提供商与路由解析、文件缺失/未知提供方/缺冒号/空模型 ID 的降级，
以及与 Java 侧共享的 ``conformance/cases.json`` 一致性用例（注释、续行、转义、重复键、BOM）。
用例全部使用 ``tempfile`` 落盘，不读仓库里的真实 ``model.properties``，不联网。
"""

import json
import tempfile
import unittest
from pathlib import Path

from model_properties import ModelProperties


CONTENT = """# 统一模型配置
deepseek.label=DeepSeek
deepseek.base-url=https://api.deepseek.com/
deepseek.api-key=test-key
deepseek.models=deepseek-flash, deepseek-v4-pro
mimo.base-url=https://api.xiaomimimo.com/v1
mimo.api-key=
mimo.models=mimo-v2.6-pro
mimo.tts-model=mimo-v2.5-tts
image.base-url=https://images.example/v1
image.capability=image
image.image-model=gpt-image-test
service.global=deepseek:deepseek-flash
service.python-a=deepseek:deepseek-v4-pro
"""


class ModelPropertiesTests(unittest.TestCase):
    """``ModelPropertiesTests`` 覆盖的解析分支。

    ``test_reads_providers_and_routes``：正常路径、选项读取、非文本能力与未知提供方；
    ``test_missing_file_and_invalid_routes``：文件缺失与三种非法路由写法；
    ``test_shared_conformance_cases``：跨语言一致性用例，含期望抛 ``ValueError`` 的非法转义。
    """
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.file = Path(self.dir.name) / "model.properties"
        self.file.write_text(CONTENT, encoding="utf-8")

    def tearDown(self):
        self.dir.cleanup()

    def test_reads_providers_and_routes(self):
        settings = ModelProperties.load(self.file)
        self.assertTrue(settings.exists)
        self.assertEqual([p.id for p in settings.text_providers()], ["deepseek", "mimo"])
        deepseek = settings.provider("deepseek")
        self.assertEqual(deepseek.base_url, "https://api.deepseek.com")
        self.assertEqual(deepseek.api_key, "test-key")
        self.assertEqual(deepseek.models, ["deepseek-flash", "deepseek-v4-pro"])
        self.assertEqual(settings.provider("mimo").option("tts-model"), "mimo-v2.5-tts")
        self.assertFalse(settings.provider("image").text)
        self.assertIsNone(settings.provider("missing"))
        self.assertEqual(settings.route("python-a").id, "deepseek:deepseek-v4-pro")
        self.assertEqual(settings.route("skill-finder").id, "deepseek:deepseek-flash")

    def test_missing_file_and_invalid_routes(self):
        missing = ModelProperties.load(Path(self.dir.name) / "missing.properties")
        self.assertFalse(missing.exists)
        self.assertEqual(list(missing.providers), [])
        self.assertIsNone(missing.route("python-a"))

        self.file.write_text(
            "deepseek.base-url=https://api.deepseek.com\n"
            "service.python-a=unknown:model\n"
            "service.skill-finder=broken\n"
            "service.personal-agent=deepseek:\n",
            encoding="utf-8",
        )
        settings = ModelProperties.load(self.file)
        self.assertIsNone(settings.route("python-a"))
        self.assertIsNone(settings.route("skill-finder"))
        self.assertIsNone(settings.route("personal-agent"))

    def test_shared_conformance_cases(self):
        conformance = Path(__file__).with_name("conformance") / "cases.json"
        cases = json.loads(conformance.read_text(encoding="utf-8"))
        for case in cases["cases"]:
            with self.subTest(case=case["name"]):
                file = Path(self.dir.name) / (case["name"] + ".properties")
                file.write_bytes(case["content"].encode("utf-8"))

                if case.get("error"):
                    with self.assertRaises(ValueError):
                        ModelProperties.load(file)
                    continue

                settings = ModelProperties.load(file)
                providers = list(settings.providers)
                self.assertEqual(len(providers), len(case["providers"]), case["name"])
                actual = []
                for provider, expected in zip(providers, case["providers"]):
                    actual.append({
                        "id": provider.id,
                        "label": provider.label,
                        "baseUrl": provider.base_url,
                        "apiKey": provider.api_key,
                        "capability": provider.capability,
                        "models": provider.models,
                        "options": {
                            name: provider.option(name)
                            for name in expected.get("options", {})
                        },
                    })
                self.assertEqual(actual, case["providers"], case["name"])

                for scope, expected_route in case["routes"].items():
                    route = settings.route(scope)
                    actual_route = None if route is None else route.id
                    self.assertEqual(actual_route, expected_route,
                                     f"{case['name']} route {scope}")


if __name__ == "__main__":
    unittest.main()
