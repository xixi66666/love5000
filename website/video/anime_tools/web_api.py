from __future__ import annotations

import json
import mimetypes
import os
import tempfile
import urllib.parse
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Callable

from anime_tools.auto_pipeline import AutoPipeline
from anime_tools.config import AppSettings
from anime_tools.openai_client import OpenAICompatibleClient
from anime_tools.project import DEFAULT_PROJECTS_ROOT
from anime_tools.project import generate_subtitles
from anime_tools.render import CommandRunner, render_image_storyboard
from anime_tools.task_manager import TaskBusyError, TaskManager


class UnsafeProjectNameError(ValueError):
    pass


class WorkbenchService:
    def __init__(
        self,
        projects_root: Path = DEFAULT_PROJECTS_ROOT,
        client_factory: Callable[[Path], Any] | None = None,
        command_runner: CommandRunner | None = None,
    ):
        self.projects_root = projects_root
        self.client_factory = client_factory or _default_client_factory
        self.command_runner = command_runner

    def list_projects(self) -> list[dict[str, Any]]:
        if not self.projects_root.is_dir():
            return []

        projects: list[dict[str, Any]] = []
        for project_dir in self.projects_root.iterdir():
            if not project_dir.is_dir():
                continue
            storyboard_path = project_dir / "storyboard.json"
            project_path = project_dir / "project.json"
            if not storyboard_path.is_file() or not project_path.is_file():
                continue
            try:
                storyboard = _read_json(storyboard_path)
                shots = _shots_from_storyboard(storyboard)
            except Exception:
                title = project_dir.name
                shot_count = 0
            else:
                title = str(storyboard.get("title") or project_dir.name)
                shot_count = len(shots)

            final_video = project_dir / "output" / "final.mp4"
            projects.append(
                {
                    "name": project_dir.name,
                    "title": title,
                    "shot_count": shot_count,
                    "has_final_video": final_video.is_file(),
                    "modified_at": project_dir.stat().st_mtime,
                }
            )

        projects.sort(key=lambda item: (item["modified_at"], item["name"]), reverse=True)
        return projects

    def get_project(self, project_name: str) -> dict[str, Any]:
        project_dir = self._project_dir(project_name)
        storyboard = _read_json(project_dir / "storyboard.json")
        narration_path = project_dir / "script" / "narration.txt"
        narration = narration_path.read_text(encoding="utf-8").strip() if narration_path.is_file() else ""

        shots = _shots_from_storyboard(storyboard)
        for shot in shots:
            shot_id = str(shot["id"])
            shot["keyframe_exists"] = (project_dir / "assets" / "keyframes" / f"{shot_id}.png").is_file()
            shot["keyframe_url"] = f"/api/assets/{project_name}/keyframes/{shot_id}.png"

        return {
            "name": project_name,
            "project_dir": str(project_dir),
            "storyboard": storyboard,
            "narration": narration,
            "assets": {
                "final_video": (project_dir / "output" / "final.mp4").is_file(),
                "subtitles": (project_dir / "output" / "subtitles.srt").is_file(),
                "voice": (project_dir / "assets" / "audio" / "voice.mp3").is_file(),
                "bgm": (project_dir / "assets" / "audio" / "bgm.mp3").is_file(),
            },
            "warnings": _read_optional_text(project_dir / "output" / "generation_warnings.md"),
        }

    def save_storyboard(self, project_name: str, storyboard: dict[str, Any], narration: str) -> dict[str, Any]:
        project_dir = self._project_dir(project_name)
        normalized = _validate_storyboard_payload(storyboard)
        clean_narration = str(narration).strip()
        if not clean_narration:
            raise ValueError("旁白不能为空")

        _atomic_write_json(project_dir / "storyboard.json", normalized)
        _atomic_write_text(project_dir / "script" / "title.txt", str(normalized.get("title", project_name)).strip() + "\n")
        _atomic_write_text(project_dir / "script" / "narration.txt", clean_narration + "\n")
        _atomic_write_json(
            project_dir / "script" / "image_prompts.json",
            {str(shot["id"]): str(shot["image_prompt"]) for shot in normalized["shots"]},
        )
        return self.get_project(project_name)

    def regenerate_keyframe(self, project_name: str, shot_id: str, config_path: str | Path) -> dict[str, Any]:
        project_dir = self._project_dir(project_name)
        storyboard = _read_json(project_dir / "storyboard.json")
        shot = _find_shot(storyboard, shot_id)
        prompt = str(shot.get("image_prompt", "")).strip()
        if not prompt:
            raise ValueError(f"镜头 {shot_id} image_prompt 不能为空")

        client = self.client_factory(Path(config_path))
        image = client.generate_image(prompt)
        image_path = project_dir / "assets" / "keyframes" / f"{shot_id}.png"
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(image)
        return {
            "shot_id": shot_id,
            "keyframe": str(image_path),
            "keyframe_exists": image_path.is_file(),
            "keyframe_url": f"/api/assets/{project_name}/keyframes/{shot_id}.png",
        }

    def generate_subtitles_for_project(self, project_name: str) -> dict[str, str]:
        project_dir = self._project_dir(project_name)
        subtitles = generate_subtitles(project_dir)
        return {"subtitles": str(subtitles)}

    def render_project_video(self, project_name: str) -> dict[str, str]:
        project_dir = self._project_dir(project_name)
        storyboard = _read_json(project_dir / "storyboard.json")
        generate_subtitles(project_dir)
        final_video = render_image_storyboard(project_dir, storyboard, self.command_runner)
        return {"final_video": str(final_video)}

    def resume_project(self, project_name: str, config_path: str | Path, bgm_path: str | Path | None = None) -> dict[str, str]:
        project_dir = self._project_dir(project_name)
        settings = AppSettings.from_json(Path(config_path))
        client = OpenAICompatibleClient(settings.openai)
        pipeline = AutoPipeline(
            projects_root=self.projects_root,
            client=client,
            default_bgm_path=Path(bgm_path) if bgm_path else settings.default_bgm,
            command_runner=self.command_runner,
        )
        result = pipeline.resume(project_dir)
        return {"project_dir": str(result.project_dir), "final_video": str(result.final_video)}

    def auto_project(self, theme: str, config_path: str | Path, bgm_path: str | Path | None = None) -> dict[str, str]:
        clean_theme = str(theme).strip()
        if not clean_theme:
            raise ValueError("主题不能为空")
        if len(clean_theme) > 300:
            raise ValueError("主题不能超过 300 字")

        settings = AppSettings.from_json(Path(config_path))
        client = OpenAICompatibleClient(settings.openai)
        pipeline = AutoPipeline(
            projects_root=self.projects_root,
            client=client,
            default_bgm_path=Path(bgm_path) if bgm_path else settings.default_bgm,
            command_runner=self.command_runner,
        )
        result = pipeline.run(clean_theme)
        return {
            "project_name": result.project_dir.name,
            "project_dir": str(result.project_dir),
            "final_video": str(result.final_video),
        }

    def _project_dir(self, project_name: str) -> Path:
        if _is_unsafe_name(project_name):
            raise UnsafeProjectNameError(f"非法项目名: {project_name}")
        project_dir = (self.projects_root / project_name).resolve()
        root = self.projects_root.resolve()
        if os.path.commonpath([str(root), str(project_dir)]) != str(root):
            raise UnsafeProjectNameError(f"非法项目路径: {project_name}")
        if not project_dir.is_dir():
            raise FileNotFoundError(f"项目不存在: {project_name}")
        return project_dir


def create_handler(
    service: WorkbenchService | None = None,
    task_manager: TaskManager | None = None,
    static_root: Path | None = None,
) -> type[BaseHTTPRequestHandler]:
    workbench = service or WorkbenchService()
    tasks = task_manager or TaskManager()
    root = static_root or Path(__file__).resolve().parent.parent / "web"

    class WorkbenchHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            try:
                self._handle_get()
            except UnsafeProjectNameError as exc:
                self._send_json({"error": str(exc)}, status=400)
            except KeyError as exc:
                self._send_json({"error": f"任务不存在: {exc}"}, status=404)
            except FileNotFoundError as exc:
                self._send_json({"error": str(exc)}, status=404)
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)

        def do_POST(self) -> None:
            try:
                self._handle_post()
            except UnsafeProjectNameError as exc:
                self._send_json({"error": str(exc)}, status=400)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
            except FileNotFoundError as exc:
                self._send_json({"error": str(exc)}, status=404)
            except TaskBusyError as exc:
                self._send_json({"error": str(exc)}, status=409)
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _handle_get(self) -> None:
            path = urllib.parse.unquote(urllib.parse.urlparse(self.path).path)
            if path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return
            if path == "/api/health":
                self._send_json({"success": True, "service": "video"})
                return
            if path == "/api/projects":
                self._send_json({"projects": workbench.list_projects()})
                return
            if path.startswith("/api/projects/"):
                project_name = path[len("/api/projects/") :]
                if "/" in project_name:
                    self._send_json({"error": "接口不存在"}, status=404)
                    return
                self._send_json(workbench.get_project(project_name))
                return
            if path.startswith("/api/tasks/"):
                task_id = path[len("/api/tasks/") :]
                self._send_json(tasks.get(task_id).to_dict())
                return
            if path.startswith("/api/assets/"):
                self._send_asset(path)
                return
            self._send_static(path)

        def _handle_post(self) -> None:
            path = urllib.parse.unquote(urllib.parse.urlparse(self.path).path)
            body = self._read_json_body()
            if path == "/api/projects/auto":
                task = tasks.submit(
                    "auto",
                    "",
                    lambda log: _run_with_logs(
                        log,
                        "开始自动生成项目",
                        lambda: workbench.auto_project(
                            body.get("theme", ""),
                            body.get("config_path") or "config.local.json",
                            body.get("bgm_path") or None,
                        ),
                    ),
                )
                self._send_json({"task": task.to_dict()}, status=202)
                return

            parts = [part for part in path.split("/") if part]
            if len(parts) >= 3 and parts[0] == "api" and parts[1] == "projects":
                project_name = parts[2]
                if len(parts) == 4 and parts[3] == "resume":
                    task = tasks.submit(
                        "resume",
                        project_name,
                        lambda log: _run_with_logs(
                            log,
                            "开始续跑项目",
                            lambda: workbench.resume_project(
                                project_name,
                                body.get("config_path") or "config.local.json",
                                body.get("bgm_path") or None,
                            ),
                        ),
                    )
                    self._send_json({"task": task.to_dict()}, status=202)
                    return
                if len(parts) == 4 and parts[3] == "storyboard":
                    saved = workbench.save_storyboard(project_name, body.get("storyboard", {}), body.get("narration", ""))
                    self._send_json(saved)
                    return
                if len(parts) == 4 and parts[3] == "subtitles":
                    self._send_json(workbench.generate_subtitles_for_project(project_name))
                    return
                if len(parts) == 4 and parts[3] == "render":
                    task = tasks.submit(
                        "render",
                        project_name,
                        lambda log: _run_with_logs(log, "开始重新合成视频", lambda: workbench.render_project_video(project_name)),
                    )
                    self._send_json({"task": task.to_dict()}, status=202)
                    return
                if len(parts) == 6 and parts[3] == "shots" and parts[5] == "regenerate-keyframe":
                    shot_id = parts[4]
                    task = tasks.submit(
                        "regenerate-keyframe",
                        project_name,
                        lambda log: _run_with_logs(
                            log,
                            f"开始重生关键帧 {shot_id}",
                            lambda: workbench.regenerate_keyframe(
                                project_name,
                                shot_id,
                                body.get("config_path") or "config.local.json",
                            ),
                        ),
                    )
                    self._send_json({"task": task.to_dict()}, status=202)
                    return
            self._send_json({"error": "接口不存在"}, status=404)

        def _send_asset(self, request_path: str) -> None:
            parts = [part for part in request_path.split("/") if part]
            if len(parts) == 5 and parts[:2] == ["api", "assets"] and parts[3] == "keyframes":
                project_dir = workbench._project_dir(parts[2])
                self._send_file(project_dir / "assets" / "keyframes" / parts[4])
                return
            if len(parts) == 5 and parts[:2] == ["api", "assets"] and parts[3] == "video" and parts[4] == "final":
                project_dir = workbench._project_dir(parts[2])
                self._send_file(project_dir / "output" / "final.mp4")
                return
            self._send_json({"error": "素材不存在"}, status=404)

        def _send_static(self, request_path: str) -> None:
            relative = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
            if _is_unsafe_static_path(relative):
                self._send_json({"error": "非法静态路径"}, status=400)
                return
            self._send_file(root / relative)

        def _send_file(self, file_path: Path) -> None:
            if not file_path.is_file():
                raise FileNotFoundError(str(file_path))
            data = file_path.read_bytes()
            content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _read_json_body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                return {}
            raw = self.rfile.read(length).decode("utf-8")
            return json.loads(raw)

        def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return WorkbenchHandler


def _is_unsafe_name(value: str) -> bool:
    return not value or value in {".", ".."} or "/" in value or "\\" in value or ".." in value


def _is_unsafe_static_path(value: str) -> bool:
    return not value or value.startswith("/") or "\\" in value or ".." in Path(value).parts


def _run_with_logs(log: Callable[[str], None], start_message: str, action: Callable[[], Any]) -> Any:
    log(start_message)
    result = action()
    log("任务完成")
    return result


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_optional_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _shots_from_storyboard(storyboard: dict[str, Any]) -> list[dict[str, Any]]:
    shots = storyboard.get("shots")
    if not isinstance(shots, list) or not shots:
        raise ValueError("storyboard.json 中 shots 必须是非空数组")
    return shots


def _find_shot(storyboard: dict[str, Any], shot_id: str) -> dict[str, Any]:
    for shot in _shots_from_storyboard(storyboard):
        if str(shot.get("id")) == shot_id:
            return shot
    raise ValueError(f"镜头不存在: {shot_id}")


def _validate_storyboard_payload(storyboard: dict[str, Any]) -> dict[str, Any]:
    title = str(storyboard.get("title", "")).strip()
    if not title:
        raise ValueError("标题不能为空")

    shots = storyboard.get("shots")
    if not isinstance(shots, list) or not shots:
        raise ValueError("shots 必须是非空数组")

    seen: set[str] = set()
    normalized_shots: list[dict[str, Any]] = []
    total_duration = 0.0
    for index, shot in enumerate(shots, start=1):
        if not isinstance(shot, dict):
            raise ValueError(f"第 {index} 个镜头格式不正确")
        shot_id = str(shot.get("id", "")).strip()
        if not shot_id:
            raise ValueError(f"第 {index} 个镜头缺少 id")
        if shot_id in seen:
            raise ValueError(f"镜头 ID 重复: {shot_id}")
        seen.add(shot_id)

        duration = float(shot.get("duration", 0))
        if duration <= 0:
            raise ValueError(f"镜头 {shot_id} duration 必须大于 0")

        description = str(shot.get("description", "")).strip()
        subtitle = str(shot.get("subtitle", "")).strip()
        image_prompt = str(shot.get("image_prompt", "")).strip()
        if not description:
            raise ValueError(f"镜头 {shot_id} description 不能为空")
        if not subtitle:
            raise ValueError(f"镜头 {shot_id} subtitle 不能为空")
        if not image_prompt:
            raise ValueError(f"镜头 {shot_id} image_prompt 不能为空")

        total_duration += duration
        normalized_shots.append(
            {
                "id": shot_id,
                "duration": duration,
                "description": description,
                "video": str(shot.get("video") or f"assets/videos/{shot_id}.mp4"),
                "subtitle": subtitle,
                "image_prompt": image_prompt,
            }
        )

    return {
        "title": title,
        "aspect_ratio": str(storyboard.get("aspect_ratio") or "9:16"),
        "duration_seconds": float(storyboard.get("duration_seconds") or total_duration),
        "style": str(storyboard.get("style") or ""),
        "shots": normalized_shots,
    }


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    _atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _atomic_write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=str(path.parent)) as file:
        file.write(value)
        temp_name = file.name
    Path(temp_name).replace(path)


def _default_client_factory(config_path: Path) -> OpenAICompatibleClient:
    settings = AppSettings.from_json(config_path)
    return OpenAICompatibleClient(settings.openai)
