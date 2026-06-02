from __future__ import annotations

import argparse
import sys
from pathlib import Path

PYTHON_ROOT = Path(__file__).resolve().parents[1]
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from anime_tools.auto_pipeline import AutoPipeline
from anime_tools.config import AppSettings, DEFAULT_CONFIG_PATH
from anime_tools.openai_client import OpenAICompatibleClient
from anime_tools.project import (
    DEFAULT_PROJECTS_ROOT,
    check_project,
    create_draft_guide,
    generate_subtitles,
    init_project,
    render_project,
)
from anime_tools.speech import create_speech_client


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI 原创动漫短片本地制作工具")
    parser.add_argument(
        "--root",
        default=str(DEFAULT_PROJECTS_ROOT),
        help="项目根目录，默认是当前工作区 anime_projects",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ["init", "check", "render", "draft"]:
        command_parser = subparsers.add_parser(name)
        command_parser.add_argument("project_name")
    auto_parser = subparsers.add_parser("auto")
    auto_parser.add_argument("theme")
    auto_parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="本地 JSON 配置文件路径",
    )
    auto_parser.add_argument(
        "--bgm",
        default=None,
        help="覆盖配置文件中的默认 BGM 文件路径",
    )
    resume_parser = subparsers.add_parser("resume-auto")
    resume_parser.add_argument("project_path")
    resume_parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="本地 JSON 配置文件路径",
    )
    resume_parser.add_argument(
        "--bgm",
        default=None,
        help="覆盖配置文件中的默认 BGM 文件路径",
    )

    args = parser.parse_args(argv)
    root = Path(args.root)

    try:
        if args.command == "init":
            created = init_project(root, args.project_name)
            print(f"项目已创建: {created}")
            return 0

        if args.command == "auto":
            settings = AppSettings.from_json(Path(args.config))
            client = OpenAICompatibleClient(settings.openai)
            speech_client = create_speech_client(settings, openai_client=client)
            default_bgm = Path(args.bgm) if args.bgm else settings.default_bgm
            pipeline = AutoPipeline(
                projects_root=root,
                client=client,
                speech_client=speech_client,
                default_bgm_path=default_bgm,
            )
            result = pipeline.run(args.theme)
            print(f"自动生成完成: {result.final_video}")
            print(f"项目目录: {result.project_dir}")
            return 0

        if args.command == "resume-auto":
            settings = AppSettings.from_json(Path(args.config))
            client = OpenAICompatibleClient(settings.openai)
            speech_client = create_speech_client(settings, openai_client=client)
            default_bgm = Path(args.bgm) if args.bgm else settings.default_bgm
            pipeline = AutoPipeline(
                projects_root=root,
                client=client,
                speech_client=speech_client,
                default_bgm_path=default_bgm,
            )
            result = pipeline.resume(Path(args.project_path))
            print(f"续跑完成: {result.final_video}")
            print(f"项目目录: {result.project_dir}")
            return 0

        project_dir = root / args.project_name

        if args.command == "check":
            result = check_project(project_dir)
            if result.ok:
                print(f"素材检查通过: {result.report_path}")
                return 0
            print(f"素材不完整，报告已生成: {result.report_path}")
            for item in result.missing_files:
                print(f"- 缺少: {item}")
            return 1

        if args.command == "render":
            generate_subtitles(project_dir)
            preview = render_project(project_dir)
            print(f"预览视频已生成: {preview}")
            return 0

        if args.command == "draft":
            guide = create_draft_guide(project_dir)
            print(f"剪映精修指南已生成: {guide}")
            return 0
    except Exception as exc:
        print(f"执行失败: {exc}", file=sys.stderr)
        return 1

    parser.error(f"未知命令: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
