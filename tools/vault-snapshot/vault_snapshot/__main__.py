"""``python -m vault_snapshot`` 的执行入口。

只负责调用 ``vault_snapshot.cli.main`` 并把其返回码交给解释器，使以模块
方式启动与通过控制台脚本启动保持完全一致的参数解析、输出与退出码语义。
"""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
