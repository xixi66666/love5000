from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PYTHON_ROOT = Path(__file__).resolve().parents[1]
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from anime_tools.config import AppSettings, DEFAULT_CONFIG_PATH, WORKSPACE_ROOT
from anime_tools.modelscope_video import DashScopeImageToVideoClient, image_file_to_data_url
from anime_tools.project import generate_subtitles, render_project


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a full project video with DashScope image-to-video clips")
    parser.add_argument("project_name", help="Project directory name under anime_projects")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Local config file path")
    parser.add_argument("--force", action="store_true", help="Regenerate shot videos even when they already exist")
    args = parser.parse_args(argv)

    project_dir = WORKSPACE_ROOT / "anime_projects" / args.project_name
    try:
        if not project_dir.is_dir():
            raise FileNotFoundError(str(project_dir))
        settings = AppSettings.from_json(Path(args.config))
        client = DashScopeImageToVideoClient(settings.modelscope_video, log=print)
        storyboard = json.loads((project_dir / "storyboard.json").read_text(encoding="utf-8"))

        for shot in storyboard["shots"]:
            shot_id = str(shot["id"])
            image_path = project_dir / "assets" / "keyframes" / f"{shot_id}.png"
            video_path = project_dir / "assets" / "videos" / f"{shot_id}.mp4"
            if video_path.is_file() and not args.force:
                print(f"Skip existing clip: {video_path}")
                continue
            prompt = _video_prompt(shot)
            print(f"Generate clip {shot_id}: {float(shot['duration']):.1f}s")
            video = client.generate_video(image_file_to_data_url(image_path), prompt)
            video_path.parent.mkdir(parents=True, exist_ok=True)
            video_path.write_bytes(video)
            print(f"Wrote clip: {video_path} ({video_path.stat().st_size} bytes)")

        generate_subtitles(project_dir)
        final = render_project(project_dir)
        print(f"Full video generated: {final.resolve()}")
        return 0
    except Exception as exc:
        print(f"Project image-to-video generation failed: {exc}", file=sys.stderr)
        return 1


def _video_prompt(shot: dict) -> str:
    parts = [
        str(shot.get("description", "")).strip(),
        str(shot.get("subtitle", "")).strip(),
        "camera slowly pushes in, subtle character and cloth motion, rain and lighting movement, cinematic anime, keep the same character and composition",
    ]
    return "；".join(part for part in parts if part)


if __name__ == "__main__":
    raise SystemExit(main())
