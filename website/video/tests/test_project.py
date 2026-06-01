import json
import tempfile
import unittest
from pathlib import Path

from anime_tools.project import (
    build_render_command,
    check_project,
    create_draft_guide,
    generate_subtitles,
    init_project,
    load_storyboard,
)


class AnimeProjectTests(unittest.TestCase):
    def test_init_project_creates_template_tree(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            project_dir = init_project(root, "001_雨夜妖刀少女")

            self.assertEqual(project_dir, root / "001_雨夜妖刀少女")
            self.assertTrue((project_dir / "project.json").is_file())
            self.assertTrue((project_dir / "storyboard.json").is_file())
            self.assertTrue((project_dir / "script" / "narration.txt").is_file())
            self.assertTrue((project_dir / "script" / "title.txt").is_file())
            self.assertTrue((project_dir / "assets" / "keyframes").is_dir())
            self.assertTrue((project_dir / "assets" / "videos").is_dir())
            self.assertTrue((project_dir / "assets" / "audio").is_dir())
            self.assertTrue((project_dir / "output").is_dir())

            storyboard = json.loads((project_dir / "storyboard.json").read_text(encoding="utf-8"))
            self.assertEqual(storyboard["aspect_ratio"], "9:16")
            self.assertEqual(len(storyboard["shots"]), 4)

    def test_check_project_reports_missing_required_assets(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = init_project(Path(temp_dir), "001_雨夜妖刀少女")

            result = check_project(project_dir)

            self.assertFalse(result.ok)
            self.assertIn("assets/videos/shot_01.mp4", result.missing_files)
            self.assertIn("assets/audio/voice.mp3", result.missing_files)
            self.assertIn("assets/audio/bgm.mp3", result.missing_files)
            self.assertTrue((project_dir / "output" / "production_report.md").is_file())

    def test_check_project_passes_when_required_assets_exist(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = init_project(Path(temp_dir), "001_雨夜妖刀少女")
            for index in range(1, 5):
                (project_dir / "assets" / "videos" / f"shot_{index:02}.mp4").write_bytes(b"fake")
            (project_dir / "assets" / "audio" / "voice.mp3").write_bytes(b"fake")
            (project_dir / "assets" / "audio" / "bgm.mp3").write_bytes(b"fake")

            result = check_project(project_dir)

            self.assertTrue(result.ok)
            self.assertEqual(result.missing_files, [])

    def test_load_storyboard_rejects_empty_shot_list(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = init_project(Path(temp_dir), "001_雨夜妖刀少女")
            (project_dir / "storyboard.json").write_text(
                json.dumps({"title": "bad", "shots": []}, ensure_ascii=False),
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                load_storyboard(project_dir)

    def test_generate_subtitles_uses_cumulative_shot_times(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = init_project(Path(temp_dir), "001_雨夜妖刀少女")

            subtitle_path = generate_subtitles(project_dir)

            content = subtitle_path.read_text(encoding="utf-8")
            self.assertIn("1\n00:00:00,000 --> 00:00:03,500", content)
            self.assertIn("2\n00:00:03,500 --> 00:00:07,000", content)
            self.assertIn("4\n00:00:11,000 --> 00:00:15,000", content)
            self.assertIn("才看见她真正的影子", content)

    def test_build_render_command_contains_inputs_and_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = init_project(Path(temp_dir), "001_雨夜妖刀少女")
            subtitles_path = generate_subtitles(project_dir)

            command = build_render_command(project_dir, subtitles_path)
            joined = " ".join(command)

            self.assertEqual(command[0], "ffmpeg")
            self.assertIn("shot_01.mp4", joined)
            self.assertIn("voice.mp3", joined)
            self.assertIn("bgm.mp3", joined)
            self.assertIn("preview.mp4", joined)
            self.assertIn("1080:1920", joined)

    def test_create_draft_guide_writes_timeline_instructions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = init_project(Path(temp_dir), "001_雨夜妖刀少女")

            guide_path = create_draft_guide(project_dir)

            content = guide_path.read_text(encoding="utf-8")
            self.assertIn("剪映手动精修指南", content)
            self.assertIn("shot_01.mp4", content)
            self.assertIn("voice.mp3", content)
            self.assertIn("bgm.mp3", content)
            self.assertTrue((project_dir / "output" / "jianying_draft").is_dir())


if __name__ == "__main__":
    unittest.main()
