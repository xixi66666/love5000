"""开奖数据分析流水线入口。

    python main.py                  # 重建全部：化验、图表、报告、操作台
    python main.py --console-only   # 只重建操作台（部署到 love5000 时用，秒级、不依赖 matplotlib）

命令行参数：
    --console-only  只重建数据操作台，跳过化验、图表与报告，因此不需要 matplotlib。
    --port          写进操作台「刷新数据」按钮的服务端口，默认 8777。`server.py` 与
                    `scripts/update_daily.py` 调用时传入实际监听端口 5179，
                    否则页面上的刷新按钮会打到没有服务监听的端口。

副作用：重建写入 `output/` 下的页面与图表产物，不修改 `data/` 下的开奖 CSV，
也不访问网络；`--port` 只影响生成进页面的配置，本模块不监听端口。

退出码：成功返回 0；参数非法由 argparse 以 2 退出；`write_console` / `run_all`
抛出的异常不在这里捕获，进程以 1 退出，调用方按非零码判定构建失败。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# `lottery` 包放在 src/ 下，以脚本方式运行时解释器不会自动找到它，必须先加入搜索路径。
sys.path.insert(0, str(ROOT / "src"))


def main() -> None:
    """按命令行开关选择重建范围。

    两条重建路径的重依赖不同：只重建操作台时不需要绘图库，因此 `lottery.console`
    只在 `--console-only` 分支内导入，`lottery.run` 同理，避免部署环境被迫安装
    matplotlib。

    Raises:
        SystemExit: argparse 在参数非法时以 2 退出；下游重建异常按原样向上抛出，
            不在这里转成返回值，`server.py` 依赖非零退出码判断构建是否成功。
    """
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
