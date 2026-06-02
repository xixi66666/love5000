from __future__ import annotations

import argparse
import sys
from pathlib import Path

PYTHON_ROOT = Path(__file__).resolve().parents[1]
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from anime_tools.config import AppSettings, DEFAULT_CONFIG_PATH, WORKSPACE_ROOT
from anime_tools.modelscope_video import DashScopeImageToVideoClient, image_file_to_data_url


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ModelScope/DashScope image-to-video API smoke test")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Local config file path")
    image_group = parser.add_mutually_exclusive_group(required=True)
    image_group.add_argument("--image-url", help="Public image URL or base64 data URL")
    image_group.add_argument("--image-file", help="Local image file. The script converts it to a base64 data URL.")
    parser.add_argument(
        "--prompt",
        default="camera slowly pushes in, cinematic anime motion, natural movement",
        help="Motion prompt",
    )
    parser.add_argument(
        "--output",
        default=str(WORKSPACE_ROOT / "anime_projects" / "modelscope_i2v_tests" / "smoke_test.mp4"),
        help="Output mp4 path",
    )
    args = parser.parse_args(argv)

    try:
        settings = AppSettings.from_json(Path(args.config))
        client = DashScopeImageToVideoClient(settings.modelscope_video, log=print)
        image_url = image_file_to_data_url(Path(args.image_file)) if args.image_file else args.image_url
        video = client.generate_video(image_url, args.prompt)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(video)
        print(f"Image-to-video test finished: {output.resolve()}")
        print(f"Bytes: {output.stat().st_size}")
        return 0
    except Exception as exc:
        print(f"Image-to-video test failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
