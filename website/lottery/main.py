"""项目入口。

    python main.py                  # 重建全部：化验、图表、报告、操作台
    python main.py --console-only   # 只重建操作台（部署到 love5000 时用，秒级、不依赖 matplotlib）
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))


def main() -> None:
    parser = argparse.ArgumentParser(description="开奖数据分析流水线")
    parser.add_argument("--console-only", action="store_true", help="只重建数据操作台")
    parser.add_argument("--port", type=int, default=8777, help="操作台服务端口（写进刷新按钮配置）")
    args = parser.parse_args()

    if args.console_only:
        from lottery.console import write_console

        write_console(port=args.port)
        return

    from lottery.run import main as run_all

    run_all()


if __name__ == "__main__":
    main()
