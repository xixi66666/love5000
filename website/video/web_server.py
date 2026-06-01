from __future__ import annotations

import argparse
from http.server import ThreadingHTTPServer
from pathlib import Path

from anime_tools.task_manager import TaskManager
from anime_tools.web_api import WorkbenchService, create_handler


def main() -> int:
    parser = argparse.ArgumentParser(description="AI 动漫生产工作台本地 Web 服务")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5176)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent / "anime_projects"))
    args = parser.parse_args()

    workspace = Path(__file__).resolve().parent
    service = WorkbenchService(projects_root=Path(args.root))
    handler = create_handler(
        service=service,
        task_manager=TaskManager(),
        static_root=workspace / "web",
    )
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"AI 动漫生产工作台已启动: http://{args.host}:{args.port}")
    print("按 Ctrl+C 停止服务")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在停止服务")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
