import base64
import json
import tempfile
import unittest
from pathlib import Path

from anime_tools.auto_pipeline import AutoPipeline, build_project_name
from anime_tools.config import AppSettings, OpenAISettings
from anime_tools.openai_client import OpenAICompatibleClient
from anime_tools.render import build_image_storyboard_command


class FakeClient:
    def generate_story_package(self, theme):
        return {
            "title": "雨夜妖刀",
            "narration": "雨夜里，刀光救下了路人。可他抬头时，看见她的影子并非人形。",
            "shots": [
                {
                    "id": "shot_01",
                    "duration": 3.5,
                    "description": "雨夜巷口，路人被黑影逼近。",
                    "subtitle": "雨夜里，他被黑影逼到墙角。",
                    "image_prompt": "国风动漫，雨夜巷口，黑影逼近路人，竖屏构图",
                },
                {
                    "id": "shot_02",
                    "duration": 3.5,
                    "description": "妖刀少女从雨幕中出现。",
                    "subtitle": "一个红黑衣袍的少女走出雨幕。",
                    "image_prompt": "国风动漫，妖刀少女，红黑衣袍，雨夜，竖屏",
                },
                {
                    "id": "shot_03",
                    "duration": 4.0,
                    "description": "刀光斩碎黑影。",
                    "subtitle": "她只出一刀，黑影便碎成烟。",
                    "image_prompt": "国风动漫，拔刀，刀光，黑影碎裂，强动势",
                },
                {
                    "id": "shot_04",
                    "duration": 4.0,
                    "description": "少女身后浮现非人影子。",
                    "subtitle": "可她身后的影子，根本不是人。",
                    "image_prompt": "国风动漫，妖刀少女背影，巨大非人妖影，雨夜",
                },
            ],
        }

    def generate_image(self, prompt):
        return b"fake-png"

    def generate_speech(self, text):
        return b"fake-mp3"


class AutoPipelineTests(unittest.TestCase):
    def test_build_project_name_uses_title_and_timestamp(self):
        name = build_project_name("雨夜妖刀", timestamp="20260601_153000")

        self.assertEqual(name, "20260601_153000_雨夜妖刀")

    def test_auto_pipeline_generates_project_assets_without_render_execution(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            bgm = root / "assets" / "default_bgm.mp3"
            bgm.parent.mkdir(parents=True)
            bgm.write_bytes(b"fake-bgm")

            calls = []

            def fake_runner(command):
                calls.append(command)
                output = Path(command[-1])
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(b"fake-mp4")

            pipeline = AutoPipeline(
                projects_root=root / "anime_projects",
                client=FakeClient(),
                default_bgm_path=bgm,
                command_runner=fake_runner,
                timestamp_provider=lambda: "20260601_153000",
            )

            result = pipeline.run("雨夜里，一个妖刀少女救下路人，但她才是真正的妖怪")

            self.assertTrue(result.project_dir.is_dir())
            self.assertTrue((result.project_dir / "storyboard.json").is_file())
            self.assertTrue((result.project_dir / "script" / "image_prompts.json").is_file())
            self.assertEqual(len(list((result.project_dir / "assets" / "keyframes").glob("shot_*.png"))), 4)
            self.assertTrue((result.project_dir / "assets" / "audio" / "voice.mp3").is_file())
            self.assertTrue((result.project_dir / "assets" / "audio" / "bgm.mp3").is_file())
            self.assertTrue((result.project_dir / "output" / "subtitles.srt").is_file())
            self.assertTrue((result.project_dir / "output" / "final.mp4").is_file())
            self.assertEqual(len(calls), 1)
            self.assertIn("final.mp4", " ".join(calls[0]))

    def test_auto_pipeline_requires_default_bgm(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pipeline = AutoPipeline(
                projects_root=Path(temp_dir) / "anime_projects",
                client=FakeClient(),
                default_bgm_path=Path(temp_dir) / "assets" / "default_bgm.mp3",
                command_runner=lambda _command: None,
            )

            with self.assertRaises(FileNotFoundError):
                pipeline.run("雨夜妖刀")

    def test_build_image_storyboard_command_uses_images_voice_bgm_subtitles_and_final_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            for relative in [
                "assets/keyframes/shot_01.png",
                "assets/keyframes/shot_02.png",
                "assets/keyframes/shot_03.png",
                "assets/keyframes/shot_04.png",
                "assets/audio/voice.mp3",
                "assets/audio/bgm.mp3",
                "output/subtitles.srt",
            ]:
                path = project_dir / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"fake")

            storyboard = {
                "shots": [
                    {"id": "shot_01", "duration": 3.5},
                    {"id": "shot_02", "duration": 3.5},
                    {"id": "shot_03", "duration": 4.0},
                    {"id": "shot_04", "duration": 4.0},
                ]
            }

            command = build_image_storyboard_command(project_dir, storyboard)
            joined = " ".join(command)

            self.assertIn("ffmpeg", command[0].lower())
            self.assertIn("shot_01.png", joined)
            self.assertIn("voice.mp3", joined)
            self.assertIn("bgm.mp3", joined)
            self.assertIn("subtitles.srt", joined)
            self.assertIn("final.mp4", joined)
            self.assertIn("zoompan", joined)

    def test_image_storyboard_command_does_not_loop_still_inputs_before_zoompan(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            storyboard = {
                "shots": [
                    {"id": "shot_01", "duration": 3.5},
                    {"id": "shot_02", "duration": 3.5},
                    {"id": "shot_03", "duration": 4.0},
                    {"id": "shot_04", "duration": 4.0},
                ]
            }

            command = build_image_storyboard_command(project_dir, storyboard)

            self.assertNotIn("-loop", command)
            self.assertNotIn("-t", command)
            self.assertIn("d=105", " ".join(command))
            self.assertIn("d=120", " ".join(command))

    def test_image_storyboard_command_keeps_video_when_voice_is_shorter_than_story(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            storyboard = {
                "shots": [
                    {"id": "shot_01", "duration": 3.5},
                    {"id": "shot_02", "duration": 3.5},
                    {"id": "shot_03", "duration": 4.0},
                    {"id": "shot_04", "duration": 4.0},
                ]
            }

            command = build_image_storyboard_command(project_dir, storyboard)
            joined = " ".join(command)

            self.assertIn("amix=inputs=2:duration=longest", joined)


class OpenAIClientTests(unittest.TestCase):
    def test_settings_normalize_base_url_and_read_model_defaults(self):
        settings = OpenAISettings(api_key="secret", base_url="https://nimabo.cn")

        self.assertEqual(settings.base_url, "https://nimabo.cn/v1")
        self.assertEqual(settings.text_model, "gpt-4.1-mini")
        self.assertEqual(settings.image_model, "gpt-image-1")
        self.assertEqual(settings.tts_model, "gpt-4o-mini-tts")

    def test_app_settings_loads_local_json_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.local.json"
            config_path.write_text(
                json.dumps(
                    {
                        "openai": {
                            "base_url": "https://nimabo.cn",
                            "api_key": "secret",
                            "text_model": "gpt-5.5",
                            "image_model": "gpt-image-2",
                            "tts_model": "gpt-4o-mini-tts",
                            "tts_voice": "alloy",
                        },
                        "assets": {
                            "default_bgm": "assets/default_bgm.mp3",
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            settings = AppSettings.from_json(config_path)

            self.assertEqual(settings.openai.base_url, "https://nimabo.cn/v1")
            self.assertEqual(settings.openai.api_key, "secret")
            self.assertEqual(settings.openai.text_model, "gpt-5.5")
            self.assertEqual(settings.openai.image_model, "gpt-image-2")
            self.assertEqual(settings.default_bgm, Path(temp_dir) / "assets" / "default_bgm.mp3")

    def test_client_parses_story_package_from_chat_completion(self):
        requests = []
        response_body = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "title": "雨夜妖刀",
                                "narration": "旁白",
                                "shots": [
                                    {
                                        "id": f"shot_{index:02}",
                                        "duration": 3.5,
                                        "description": "画面",
                                        "subtitle": "字幕",
                                        "image_prompt": "提示词",
                                    }
                                    for index in range(1, 5)
                                ],
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

        def transport(method, url, headers, payload):
            requests.append((method, url, headers, payload))
            return 200, {"content-type": "application/json"}, json.dumps(response_body).encode("utf-8")

        client = OpenAICompatibleClient(OpenAISettings(api_key="secret"), transport=transport)
        package = client.generate_story_package("雨夜妖刀")

        self.assertEqual(package["title"], "雨夜妖刀")
        self.assertEqual(requests[0][0], "POST")
        self.assertTrue(requests[0][1].endswith("/chat/completions"))
        self.assertNotIn("secret", json.dumps(requests[0][3], ensure_ascii=False))

    def test_client_decodes_base64_image_response(self):
        image = base64.b64encode(b"image-bytes").decode("ascii")

        def transport(method, url, headers, payload):
            return 200, {"content-type": "application/json"}, json.dumps({"data": [{"b64_json": image}]}).encode("utf-8")

        client = OpenAICompatibleClient(OpenAISettings(api_key="secret"), transport=transport)

        self.assertEqual(client.generate_image("提示词"), b"image-bytes")

    def test_client_returns_speech_binary(self):
        def transport(method, url, headers, payload):
            return 200, {"content-type": "audio/mpeg"}, b"mp3-bytes"

        client = OpenAICompatibleClient(OpenAISettings(api_key="secret"), transport=transport)

        self.assertEqual(client.generate_speech("旁白"), b"mp3-bytes")


if __name__ == "__main__":
    unittest.main()
