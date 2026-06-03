from __future__ import annotations

import base64
import json
import sys
import tempfile
import unittest
from pathlib import Path


VIDEO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = VIDEO_ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from anime_tools.auto_pipeline import AutoPipeline
from anime_tools.config import AppSettings
from anime_tools.image_to_video import ImageToVideoRequest
from anime_tools.local_wan_video import LocalWanImageToVideoProvider


class FakeStoryClient:
    def generate_story_package(self, theme: str) -> dict:
        return {
            "title": "Wan测试",
            "narration": "一束光穿过云层。",
            "shots": [
                {
                    "id": "shot_01",
                    "duration": 3.5,
                    "description": "云层中出现光束",
                    "subtitle": "光从云里落下。",
                    "image_prompt": "国风动漫，云层，光束，电影感",
                },
                {
                    "id": "shot_02",
                    "duration": 3.5,
                    "description": "少年抬头",
                    "subtitle": "少年抬起头。",
                    "image_prompt": "国风动漫，少年，逆光，电影感",
                },
            ],
        }

    def generate_image(self, prompt: str) -> bytes:
        return b"fake-png"


class FakeSpeechClient:
    def generate_speech(self, text: str) -> bytes:
        return b"fake-mp3"


class FakeImageToVideoProvider:
    def __init__(self) -> None:
        self.requests: list[ImageToVideoRequest] = []

    def generate(self, request: ImageToVideoRequest) -> bytes:
        self.requests.append(request)
        return f"video:{request.shot_id}:{request.prompt}".encode("utf-8")


class ImageToVideoExtensionTests(unittest.TestCase):
    def test_config_loads_local_wan_image_to_video_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config_path = Path(temp) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "openai": {
                            "api_key": "test-key",
                            "base_url": "http://127.0.0.1:9999/v1",
                        },
                        "tts": {"provider": "openai"},
                        "image_to_video": {
                            "enabled": True,
                            "provider": "local_wan",
                        },
                        "local_wan_video": {
                            "base_url": "http://127.0.0.1:7860",
                            "endpoint": "/generate",
                            "timeout_seconds": 123,
                        },
                        "assets": {"default_bgm": "assets/default_bgm.mp3"},
                    }
                ),
                encoding="utf-8",
            )

            settings = AppSettings.from_json(config_path)

        self.assertTrue(settings.image_to_video.enabled)
        self.assertEqual("local_wan", settings.image_to_video.provider)
        self.assertEqual("http://127.0.0.1:7860", settings.local_wan_video.base_url)
        self.assertEqual("/generate", settings.local_wan_video.endpoint)
        self.assertEqual(123, settings.local_wan_video.timeout_seconds)

    def test_auto_pipeline_generates_shot_videos_when_provider_is_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bgm = root / "default_bgm.mp3"
            bgm.write_bytes(b"fake-bgm")
            provider = FakeImageToVideoProvider()
            captured_commands: list[list[str]] = []

            def capture_command(command: list[str]) -> None:
                captured_commands.append(command)

            pipeline = AutoPipeline(
                projects_root=root / "projects",
                client=FakeStoryClient(),
                speech_client=FakeSpeechClient(),
                default_bgm_path=bgm,
                image_to_video_provider=provider,
                command_runner=capture_command,
                timestamp_provider=lambda: "20260603_000000",
            )

            result = pipeline.run("测试主题")

            shot_01_video = result.project_dir / "assets" / "videos" / "shot_01.mp4"
            shot_02_video = result.project_dir / "assets" / "videos" / "shot_02.mp4"
            self.assertTrue(shot_01_video.is_file())
            self.assertTrue(shot_02_video.is_file())
            self.assertEqual(2, len(provider.requests))
            self.assertEqual("shot_01", provider.requests[0].shot_id)
            self.assertEqual(result.project_dir / "assets" / "keyframes" / "shot_01.png", provider.requests[0].image_path)
            self.assertEqual("国风动漫，云层，光束，电影感", provider.requests[0].prompt)
            self.assertEqual(3.5, provider.requests[0].duration)
            rendered_command = " ".join(captured_commands[0])
            self.assertIn("assets\\videos\\shot_01.mp4", rendered_command)
            self.assertNotIn("assets\\keyframes\\shot_01.png", rendered_command)

    def test_local_wan_provider_accepts_base64_video_response(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            image_path = Path(temp) / "shot.png"
            image_path.write_bytes(b"fake-png")
            payloads = []

            def fake_transport(method, url, headers, payload, timeout):
                payloads.append(payload)
                body = json.dumps(
                    {
                        "video_base64": base64.b64encode(b"fake-video").decode("ascii"),
                    }
                ).encode("utf-8")
                return 200, {"content-type": "application/json"}, body

            provider = LocalWanImageToVideoProvider(
                base_url="http://127.0.0.1:7860",
                endpoint="/generate",
                timeout_seconds=30,
                transport=fake_transport,
            )

            video = provider.generate(
                ImageToVideoRequest(
                    project_dir=Path(temp),
                    shot_id="shot_01",
                    image_path=image_path,
                    prompt="镜头缓慢推进",
                    duration=5,
                    resolution="720P",
                )
            )

        self.assertEqual(b"fake-video", video)
        self.assertEqual("shot_01", payloads[0]["shot_id"])
        self.assertEqual("镜头缓慢推进", payloads[0]["prompt"])
        self.assertTrue(payloads[0]["image"].startswith("data:image/png;base64,"))


if __name__ == "__main__":
    unittest.main()
