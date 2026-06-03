from __future__ import annotations

import json
import re
import shutil
import wave
from array import array
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from anime_tools.image_to_video import ImageToVideoProvider, ImageToVideoRequest
from anime_tools.project import DEFAULT_PROJECTS_ROOT, generate_subtitles
from anime_tools.project import render_project as render_video_storyboard
from anime_tools.render import CommandRunner, render_image_storyboard


@dataclass(frozen=True)
class AutoPipelineResult:
    project_dir: Path
    final_video: Path


class AutoPipeline:
    def __init__(
        self,
        projects_root: Path = DEFAULT_PROJECTS_ROOT,
        client: Any | None = None,
        speech_client: Any | None = None,
        default_bgm_path: Path | None = None,
        image_to_video_provider: ImageToVideoProvider | None = None,
        command_runner: CommandRunner | None = None,
        timestamp_provider: Callable[[], str] | None = None,
    ):
        self.projects_root = projects_root
        self.client = client
        self.speech_client = speech_client or client
        self.default_bgm_path = default_bgm_path or Path(__file__).resolve().parent.parent / "assets" / "default_bgm.mp3"
        self.image_to_video_provider = image_to_video_provider
        self.command_runner = command_runner
        self.timestamp_provider = timestamp_provider or (lambda: datetime.now().strftime("%Y%m%d_%H%M%S"))

    def run(self, theme: str) -> AutoPipelineResult:
        if self.client is None:
            raise RuntimeError("AutoPipeline 需要 client")
        if not self.default_bgm_path.is_file():
            raise FileNotFoundError(f"缺少默认 BGM: {self.default_bgm_path}")

        package = self.client.generate_story_package(theme)
        project_name = build_project_name(package["title"], self.timestamp_provider())
        project_dir = self.projects_root / project_name
        _create_auto_tree(project_dir)

        storyboard = _package_to_storyboard(package)
        _write_json(project_dir / "project.json", {"name": project_name, "type": "ai_anime_auto", "version": "0.2.0"})
        _write_json(project_dir / "storyboard.json", storyboard)
        _write_text(project_dir / "script" / "title.txt", package["title"] + "\n")
        _write_text(project_dir / "script" / "narration.txt", package["narration"] + "\n")
        _write_json(
            project_dir / "script" / "image_prompts.json",
            {shot["id"]: shot["image_prompt"] for shot in package["shots"]},
        )

        for shot in package["shots"]:
            image = self.client.generate_image(shot["image_prompt"])
            (project_dir / "assets" / "keyframes" / f"{shot['id']}.png").write_bytes(image)

        self._generate_shot_videos(project_dir, storyboard)
        speech = self.speech_client.generate_speech(package["narration"])
        (project_dir / "assets" / "audio" / "voice.mp3").write_bytes(speech)
        shutil.copyfile(self.default_bgm_path, project_dir / "assets" / "audio" / "bgm.mp3")

        generate_subtitles(project_dir)
        final_video = self._render_project(project_dir, storyboard)
        _write_generation_report(project_dir, theme, package)
        return AutoPipelineResult(project_dir=project_dir, final_video=final_video)

    def resume(self, project_dir: Path) -> AutoPipelineResult:
        if self.client is None:
            raise RuntimeError("AutoPipeline 需要 client")
        if not self.default_bgm_path.is_file():
            raise FileNotFoundError(f"缺少默认 BGM: {self.default_bgm_path}")

        storyboard = json.loads((project_dir / "storyboard.json").read_text(encoding="utf-8"))
        narration = (project_dir / "script" / "narration.txt").read_text(encoding="utf-8").strip()

        for shot in storyboard["shots"]:
            image_path = project_dir / "assets" / "keyframes" / f"{shot['id']}.png"
            if not image_path.is_file():
                image = self.client.generate_image(shot["image_prompt"])
                image_path.write_bytes(image)

        self._generate_shot_videos(project_dir, storyboard, skip_existing=True)
        voice_path = project_dir / "assets" / "audio" / "voice.mp3"
        if not voice_path.is_file():
            try:
                voice_path.write_bytes(self.speech_client.generate_speech(narration))
            except Exception as exc:
                _write_silent_audio(voice_path, _storyboard_duration(storyboard))
                _append_warning(project_dir, f"TTS 生成失败，已使用静音占位音频：{exc}")

        bgm_path = project_dir / "assets" / "audio" / "bgm.mp3"
        if not bgm_path.is_file():
            shutil.copyfile(self.default_bgm_path, bgm_path)

        generate_subtitles(project_dir)
        final_video = self._render_project(project_dir, storyboard)
        return AutoPipelineResult(project_dir=project_dir, final_video=final_video)

    def _generate_shot_videos(self, project_dir: Path, storyboard: dict[str, Any], skip_existing: bool = False) -> None:
        if self.image_to_video_provider is None:
            return

        videos_dir = project_dir / "assets" / "videos"
        videos_dir.mkdir(parents=True, exist_ok=True)
        for shot in storyboard["shots"]:
            shot_id = str(shot["id"])
            video_path = videos_dir / f"{shot_id}.mp4"
            if skip_existing and video_path.is_file():
                continue
            image_path = project_dir / "assets" / "keyframes" / f"{shot_id}.png"
            video = self.image_to_video_provider.generate(
                ImageToVideoRequest(
                    project_dir=project_dir,
                    shot_id=shot_id,
                    image_path=image_path,
                    prompt=str(shot.get("image_prompt", "")),
                    duration=float(shot["duration"]),
                )
            )
            video_path.write_bytes(video)

    def _render_project(self, project_dir: Path, storyboard: dict[str, Any]) -> Path:
        if self._has_all_shot_videos(project_dir, storyboard):
            preview = render_video_storyboard(project_dir, self.command_runner)
            final = project_dir / "output" / "final.mp4"
            if preview.is_file() and preview != final:
                shutil.copyfile(preview, final)
            return final
        return render_image_storyboard(project_dir, storyboard, self.command_runner)

    def _has_all_shot_videos(self, project_dir: Path, storyboard: dict[str, Any]) -> bool:
        return all((project_dir / "assets" / "videos" / f"{shot['id']}.mp4").is_file() for shot in storyboard["shots"])


def build_project_name(title: str, timestamp: str | None = None) -> str:
    safe_title = re.sub(r'[\\/:*?"<>|\s]+', "", title).strip() or "AI动漫短片"
    safe_title = safe_title[:16]
    prefix = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{safe_title}"


def _create_auto_tree(project_dir: Path) -> None:
    for relative_dir in [
        "script",
        "assets/keyframes",
        "assets/videos",
        "assets/audio",
        "output",
    ]:
        (project_dir / relative_dir).mkdir(parents=True, exist_ok=True)


def _package_to_storyboard(package: dict[str, Any]) -> dict[str, Any]:
    shots = []
    for shot in package["shots"]:
        shots.append(
            {
                "id": shot["id"],
                "duration": float(shot["duration"]),
                "description": shot["description"],
                "video": f"assets/videos/{shot['id']}.mp4",
                "subtitle": shot["subtitle"],
                "image_prompt": shot["image_prompt"],
            }
        )
    return {
        "title": package["title"],
        "aspect_ratio": "9:16",
        "duration_seconds": sum(float(shot["duration"]) for shot in shots),
        "style": "国风玄幻，动漫动态分镜，电影感，竖屏",
        "shots": shots,
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _write_generation_report(project_dir: Path, theme: str, package: dict[str, Any]) -> None:
    lines = [
        "# 自动生成报告",
        "",
        f"- 主题：{theme}",
        f"- 标题：{package['title']}",
        f"- 镜头数：{len(package['shots'])}",
        "- 输出：`output/final.mp4`",
        "",
        "## 镜头",
        "",
    ]
    for shot in package["shots"]:
        lines.extend(
            [
                f"### {shot['id']}",
                "",
                f"- 时长：{shot['duration']} 秒",
                f"- 字幕：{shot['subtitle']}",
                f"- 提示词：{shot['image_prompt']}",
                "",
            ]
        )
    (project_dir / "output" / "generation_report.md").write_text("\n".join(lines), encoding="utf-8")


def _storyboard_duration(storyboard: dict[str, Any]) -> float:
    return sum(float(shot["duration"]) for shot in storyboard["shots"])


def _write_silent_audio(path: Path, duration_seconds: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 44100
    samples = array("h", [0]) * int(sample_rate * duration_seconds)
    # 文件扩展名沿用 mp3，FFmpeg 会根据 WAV 头正确识别输入。
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(samples.tobytes())


def _append_warning(project_dir: Path, message: str) -> None:
    report = project_dir / "output" / "generation_warnings.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    with report.open("a", encoding="utf-8") as file:
        file.write(f"- {message}\n")
