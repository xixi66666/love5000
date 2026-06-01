import json
import tempfile
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from anime_tools.web_api import UnsafeProjectNameError, WorkbenchService, create_handler


class WorkbenchServiceTests(unittest.TestCase):
    def test_list_projects_reads_existing_project_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_project(root / "20260601_111111_短片A", "短片A", 2)
            _write_project(root / "20260601_222222_短片B", "短片B", 5)
            (root / "not_a_project").mkdir()

            service = WorkbenchService(projects_root=root)

            projects = service.list_projects()

            self.assertEqual([item["name"] for item in projects], ["20260601_222222_短片B", "20260601_111111_短片A"])
            self.assertEqual(projects[0]["title"], "短片B")
            self.assertEqual(projects[0]["shot_count"], 5)

    def test_rejects_unsafe_project_names(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = WorkbenchService(projects_root=Path(temp_dir))

            with self.assertRaises(UnsafeProjectNameError):
                service.get_project("..\\config.local.json")

            with self.assertRaises(UnsafeProjectNameError):
                service.get_project("../outside")

    def test_get_project_returns_dynamic_shots_and_assets(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project_dir = _write_project(root / "long_project", "长片", 6)
            (project_dir / "assets" / "keyframes" / "shot_03.png").write_bytes(b"fake-png")
            (project_dir / "output" / "final.mp4").write_bytes(b"fake-video")

            service = WorkbenchService(projects_root=root)

            detail = service.get_project("long_project")

            self.assertEqual(detail["name"], "long_project")
            self.assertEqual(detail["storyboard"]["title"], "长片")
            self.assertEqual(len(detail["storyboard"]["shots"]), 6)
            self.assertTrue(detail["assets"]["final_video"])
            self.assertTrue(detail["storyboard"]["shots"][2]["keyframe_exists"])

    def test_save_storyboard_keeps_more_than_four_shots_and_updates_script_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_project(root / "long_project", "旧标题", 4)
            service = WorkbenchService(projects_root=root)
            storyboard = _storyboard("新标题", 7)
            narration = "这是一段新的长片旁白。"

            saved = service.save_storyboard("long_project", storyboard, narration)

            self.assertEqual(len(saved["storyboard"]["shots"]), 7)
            project_dir = root / "long_project"
            disk_storyboard = json.loads((project_dir / "storyboard.json").read_text(encoding="utf-8"))
            image_prompts = json.loads((project_dir / "script" / "image_prompts.json").read_text(encoding="utf-8"))
            self.assertEqual(disk_storyboard["title"], "新标题")
            self.assertEqual((project_dir / "script" / "title.txt").read_text(encoding="utf-8"), "新标题\n")
            self.assertEqual((project_dir / "script" / "narration.txt").read_text(encoding="utf-8"), narration + "\n")
            self.assertEqual(len(image_prompts), 7)
            self.assertEqual(image_prompts["shot_07"], "提示词 7")

    def test_save_storyboard_rejects_duplicate_shot_ids(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_project(root / "bad_project", "坏项目", 2)
            service = WorkbenchService(projects_root=root)
            storyboard = _storyboard("坏项目", 2)
            storyboard["shots"][1]["id"] = "shot_01"

            with self.assertRaises(ValueError):
                service.save_storyboard("bad_project", storyboard, "旁白")

    def test_regenerate_keyframe_uses_current_prompt_and_writes_png(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_project(root / "image_project", "图片项目", 3)
            client = FakeClient()
            service = WorkbenchService(projects_root=root, client_factory=lambda _config: client)

            result = service.regenerate_keyframe("image_project", "shot_03", config_path="config.local.json")

            image_path = root / "image_project" / "assets" / "keyframes" / "shot_03.png"
            self.assertEqual(image_path.read_bytes(), b"new-image")
            self.assertEqual(client.prompts, ["提示词 3"])
            self.assertTrue(result["keyframe_exists"])

    def test_generate_subtitles_for_project_writes_srt(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_project(root / "subtitle_project", "字幕项目", 2)
            service = WorkbenchService(projects_root=root)

            result = service.generate_subtitles_for_project("subtitle_project")

            self.assertTrue(Path(result["subtitles"]).is_file())
            self.assertIn("00:00:03,500", Path(result["subtitles"]).read_text(encoding="utf-8"))

    def test_render_project_video_uses_injected_runner(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project_dir = _write_project(root / "render_project", "渲染项目", 2)
            for relative in [
                "assets/keyframes/shot_01.png",
                "assets/keyframes/shot_02.png",
                "assets/audio/voice.mp3",
                "assets/audio/bgm.mp3",
            ]:
                path = project_dir / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"fake")
            calls = []

            def runner(command):
                calls.append(command)
                Path(command[-1]).write_bytes(b"fake-video")

            service = WorkbenchService(projects_root=root, command_runner=runner)

            result = service.render_project_video("render_project")

            self.assertTrue(Path(result["final_video"]).is_file())
            self.assertEqual(len(calls), 1)
            self.assertIn("final.mp4", " ".join(calls[0]))


class WorkbenchHttpTests(unittest.TestCase):
    def test_http_health_reports_video_service_ready(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = WorkbenchService(projects_root=Path(temp_dir))
            server = _start_server(service)
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"

                health = _get_json(base_url + "/api/health")

                self.assertTrue(health["success"])
                self.assertEqual(health["service"], "video")
            finally:
                server.shutdown()
                server.server_close()

    def test_http_projects_detail_storyboard_and_static_index(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_project(root / "http_project", "HTTP项目", 5)
            service = WorkbenchService(projects_root=root)
            server = _start_server(service)
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"

                projects = _get_json(base_url + "/api/projects")
                self.assertEqual(projects["projects"][0]["name"], "http_project")

                detail = _get_json(base_url + "/api/projects/http_project")
                self.assertEqual(len(detail["storyboard"]["shots"]), 5)

                updated = _storyboard("HTTP新标题", 6)
                response = _post_json(
                    base_url + "/api/projects/http_project/storyboard",
                    {"storyboard": updated, "narration": "新旁白"},
                )
                self.assertEqual(len(response["storyboard"]["shots"]), 6)

                html = urllib.request.urlopen(base_url + "/", timeout=2).read().decode("utf-8")
                self.assertIn("AI 动漫生产工作台", html)
            finally:
                server.shutdown()
                server.server_close()

    def test_http_rejects_unsafe_project_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = WorkbenchService(projects_root=Path(temp_dir))
            server = _start_server(service)
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"
                with self.assertRaises(urllib.error.HTTPError) as raised:
                    urllib.request.urlopen(base_url + "/api/projects/..%5Csecret", timeout=2)
                self.assertEqual(raised.exception.code, 400)
            finally:
                server.shutdown()
                server.server_close()

    def test_http_favicon_does_not_report_missing_resource(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = WorkbenchService(projects_root=Path(temp_dir))
            server = _start_server(service)
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"
                response = urllib.request.urlopen(base_url + "/favicon.ico", timeout=2)
                self.assertEqual(response.status, 204)
            finally:
                server.shutdown()
                server.server_close()


def _write_project(project_dir: Path, title: str, shot_count: int) -> Path:
    (project_dir / "script").mkdir(parents=True)
    (project_dir / "assets" / "keyframes").mkdir(parents=True)
    (project_dir / "assets" / "audio").mkdir(parents=True)
    (project_dir / "output").mkdir(parents=True)
    (project_dir / "project.json").write_text(
        json.dumps({"name": project_dir.name, "type": "ai_anime_auto"}, ensure_ascii=False),
        encoding="utf-8",
    )
    storyboard = _storyboard(title, shot_count)
    (project_dir / "storyboard.json").write_text(json.dumps(storyboard, ensure_ascii=False), encoding="utf-8")
    (project_dir / "script" / "title.txt").write_text(title + "\n", encoding="utf-8")
    (project_dir / "script" / "narration.txt").write_text("旁白\n", encoding="utf-8")
    return project_dir


def _storyboard(title: str, shot_count: int) -> dict:
    shots = []
    for index in range(1, shot_count + 1):
        shots.append(
            {
                "id": f"shot_{index:02}",
                "duration": 3.5,
                "description": f"描述 {index}",
                "subtitle": f"字幕 {index}",
                "image_prompt": f"提示词 {index}",
                "video": f"assets/videos/shot_{index:02}.mp4",
            }
        )
    return {
        "title": title,
        "aspect_ratio": "9:16",
        "duration_seconds": shot_count * 3.5,
        "style": "国风动漫",
        "shots": shots,
    }


class FakeClient:
    def __init__(self):
        self.prompts = []

    def generate_image(self, prompt):
        self.prompts.append(prompt)
        return b"new-image"


def _start_server(service):
    handler = create_handler(service, static_root=Path(__file__).resolve().parent.parent / "web")
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _get_json(url):
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        raise AssertionError(f"GET {url} failed with {exc.code}: {body}") from exc


def _post_json(url, body):
    request = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=2) as response:
        return json.loads(response.read().decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
