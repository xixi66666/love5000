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


if __name__ == "__main__":
    unittest.main()
