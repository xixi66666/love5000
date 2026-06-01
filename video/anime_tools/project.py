from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_PROJECTS_ROOT = Path(__file__).resolve().parent.parent / "anime_projects"


DEFAULT_STORYBOARD: dict[str, Any] = {
    "title": "雨夜妖刀少女",
    "aspect_ratio": "9:16",
    "duration_seconds": 15,
    "style": "国风玄幻，冷艳杀伐，雨夜，红黑配色，电影感动漫",
    "shots": [
        {
            "id": "shot_01",
            "duration": 3.5,
            "description": "雨夜巷口，一个路人被黑影逼到墙角。",
            "video": "assets/videos/shot_01.mp4",
            "subtitle": "那晚，他以为自己遇见了救命恩人。",
        },
        {
            "id": "shot_02",
            "duration": 3.5,
            "description": "红黑衣袍的妖刀少女撑伞出现，雨水从刀鞘滑落。",
            "video": "assets/videos/shot_02.mp4",
            "subtitle": "雨声里，一个少女从黑暗中走来。",
        },
        {
            "id": "shot_03",
            "duration": 4,
            "description": "少女拔刀，刀光掠过，黑影被斩碎。",
            "video": "assets/videos/shot_03.mp4",
            "subtitle": "她只出了一刀，妖影便碎成满地黑烟。",
        },
        {
            "id": "shot_04",
            "duration": 4,
            "description": "路人低头道谢，再抬头时，看见少女身后的影子不是人形。",
            "video": "assets/videos/shot_04.mp4",
            "subtitle": "可他抬头的瞬间，才看见她真正的影子。",
        },
    ],
}


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    missing_files: list[str]
    report_path: Path


def init_project(projects_root: Path, project_name: str) -> Path:
    project_dir = projects_root / project_name
    for relative_dir in [
        "script",
        "assets/keyframes",
        "assets/videos",
        "assets/audio",
        "output",
    ]:
        (project_dir / relative_dir).mkdir(parents=True, exist_ok=True)

    project = {
        "name": project_name,
        "type": "ai_anime_short",
        "version": "0.1.0",
    }
    _write_json_if_missing(project_dir / "project.json", project)
    _write_json_if_missing(project_dir / "storyboard.json", DEFAULT_STORYBOARD)
    _write_text_if_missing(project_dir / "script" / "title.txt", "雨夜妖刀少女\n")
    _write_text_if_missing(
        project_dir / "script" / "narration.txt",
        "\n".join(shot["subtitle"] for shot in DEFAULT_STORYBOARD["shots"]) + "\n",
    )
    return project_dir


def load_storyboard(project_dir: Path) -> dict[str, Any]:
    storyboard_path = project_dir / "storyboard.json"
    if not storyboard_path.is_file():
        raise FileNotFoundError(f"缺少分镜配置文件: {storyboard_path}")

    storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
    shots = storyboard.get("shots")
    if not isinstance(shots, list) or not shots:
        raise ValueError("storyboard.json 中 shots 必须是非空数组")

    for index, shot in enumerate(shots, start=1):
        for field in ["id", "duration", "video", "subtitle"]:
            if field not in shot:
                raise ValueError(f"第 {index} 个镜头缺少字段: {field}")
        if float(shot["duration"]) <= 0:
            raise ValueError(f"第 {index} 个镜头 duration 必须大于 0")
    return storyboard


def check_project(project_dir: Path) -> CheckResult:
    storyboard = load_storyboard(project_dir)
    required = [shot["video"] for shot in storyboard["shots"]]
    required.extend(["assets/audio/voice.mp3", "assets/audio/bgm.mp3"])

    missing = [relative for relative in required if not (project_dir / relative).is_file()]
    report_path = _write_production_report(project_dir, missing)
    return CheckResult(ok=not missing, missing_files=missing, report_path=report_path)


def generate_subtitles(project_dir: Path) -> Path:
    storyboard = load_storyboard(project_dir)
    output_path = project_dir / "output" / "subtitles.srt"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    current = 0.0
    blocks: list[str] = []
    for index, shot in enumerate(storyboard["shots"], start=1):
        start = current
        current += float(shot["duration"])
        blocks.append(
            f"{index}\n"
            f"{_format_srt_time(start)} --> {_format_srt_time(current)}\n"
            f"{shot['subtitle']}\n"
        )

    output_path.write_text("\n".join(blocks), encoding="utf-8")
    return output_path


def build_render_command(project_dir: Path, subtitles_path: Path | None = None) -> list[str]:
    storyboard = load_storyboard(project_dir)
    subtitles = subtitles_path or project_dir / "output" / "subtitles.srt"
    preview = project_dir / "output" / "preview.mp4"
    voice = project_dir / "assets" / "audio" / "voice.mp3"
    bgm = project_dir / "assets" / "audio" / "bgm.mp3"
    shots = storyboard["shots"]
    total_duration = sum(float(shot["duration"]) for shot in shots)
    fade_out_start = max(total_duration - 0.35, 0)

    escaped_subtitles = _ffmpeg_path(subtitles)
    command = ["ffmpeg", "-y"]
    for shot in shots:
        command.extend(["-i", str(project_dir / shot["video"])])
    command.extend(["-i", str(voice), "-i", str(bgm)])

    scaled_labels = []
    filters = []
    for index, _shot in enumerate(shots):
        label = f"v{index}"
        scaled_labels.append(f"[{label}]")
        filters.append(
            f"[{index}:v]scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,setsar=1[{label}]"
        )

    voice_index = len(shots)
    bgm_index = len(shots) + 1
    filters.extend(
        [
            f"{''.join(scaled_labels)}concat=n={len(shots)}:v=1:a=0,"
            f"fade=t=in:st=0:d=0.35,"
            f"fade=t=out:st={fade_out_start:.2f}:d=0.35,"
            f"subtitles='{escaped_subtitles}'[v]",
            f"[{voice_index}:a]volume=1.0[a1]",
            f"[{bgm_index}:a]volume=0.18[a2]",
            "[a1][a2]amix=inputs=2:duration=first[a]",
        ]
    )

    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-shortest",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(preview),
        ]
    )
    return command


def render_project(project_dir: Path) -> Path:
    check = check_project(project_dir)
    if not check.ok:
        raise FileNotFoundError("素材不完整，请先运行 check 查看 output/production_report.md")

    subtitles = generate_subtitles(project_dir)
    command = build_render_command(project_dir, subtitles)
    subprocess.run(command, check=True)
    return project_dir / "output" / "preview.mp4"


def create_draft_guide(project_dir: Path) -> Path:
    storyboard = load_storyboard(project_dir)
    output_dir = project_dir / "output"
    draft_dir = output_dir / "jianying_draft"
    draft_dir.mkdir(parents=True, exist_ok=True)

    lines = [
        "# 剪映手动精修指南",
        "",
        "## 素材",
        "",
        "- 旁白：`assets/audio/voice.mp3`",
        "- BGM：`assets/audio/bgm.mp3`",
        "- 字幕：`output/subtitles.srt`",
        "",
        "## 时间线",
        "",
    ]
    current = 0.0
    for shot in storyboard["shots"]:
        end = current + float(shot["duration"])
        lines.extend(
            [
                f"- `{shot['video']}`",
                f"  - 时间：{current:.1f}s - {end:.1f}s",
                f"  - 字幕：{shot['subtitle']}",
                f"  - 画面：{shot.get('description', '')}",
                "",
            ]
        )
        current = end

    lines.extend(
        [
            "## 剪映建议",
            "",
            "1. 新建 9:16 竖屏项目。",
            "2. 按时间线顺序导入 4 个镜头视频。",
            "3. 导入旁白和 BGM，BGM 音量建议 15%-25%。",
            "4. 导入或手动复制 `output/subtitles.srt` 字幕。",
            "5. 检查最后一个镜头的影子反转是否清楚，再导出成片。",
        ]
    )

    guide_path = output_dir / "manual_cutting_guide.md"
    guide_path.write_text("\n".join(lines), encoding="utf-8")
    (draft_dir / "README.md").write_text(
        "这里预留给剪映草稿实验文件。当前版本优先使用 manual_cutting_guide.md 手动精修。\n",
        encoding="utf-8",
    )
    return guide_path


def _write_concat_file(project_dir: Path) -> Path:
    storyboard = load_storyboard(project_dir)
    concat_file = project_dir / "output" / "videos.txt"
    lines = []
    for shot in storyboard["shots"]:
        path = (project_dir / shot["video"]).resolve()
        lines.append(f"file '{path.as_posix()}'")
    concat_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return concat_file


def _write_json_if_missing(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        return
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text_if_missing(path: Path, value: str) -> None:
    if path.exists():
        return
    path.write_text(value, encoding="utf-8")


def _write_production_report(project_dir: Path, missing: list[str]) -> Path:
    output_dir = project_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "production_report.md"
    if missing:
        body = ["# 制作检查报告", "", "## 缺失素材", ""]
        body.extend(f"- `{item}`" for item in missing)
    else:
        body = ["# 制作检查报告", "", "素材检查通过，可以执行 render。"]
    report_path.write_text("\n".join(body) + "\n", encoding="utf-8")
    return report_path


def _format_srt_time(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours = milliseconds // 3_600_000
    milliseconds %= 3_600_000
    minutes = milliseconds // 60_000
    milliseconds %= 60_000
    secs = milliseconds // 1000
    millis = milliseconds % 1000
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def _ffmpeg_path(path: Path) -> str:
    # FFmpeg subtitles filter on Windows needs escaped drive colon and forward slashes.
    text = path.resolve().as_posix()
    if len(text) > 1 and text[1] == ":":
        text = text[0] + r"\:" + text[2:]
    return text.replace("'", r"\'")
