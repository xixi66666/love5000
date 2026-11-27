"""Vault 快照工具的公开包入口。

``vault_snapshot`` 是一个离线、仅依赖 Python 标准库的独立 CLI，负责创建、
校验和恢复显式指定的 Vault 快照：不读取 home 目录、临时目录或任何隐式
默认路径，所有路径都必须由调用方给出。

本模块只做转发，把 ``vault_snapshot.core`` 中的格式常量、数据类、异常和
三个对外函数重新导出，保证 ``from vault_snapshot import create_snapshot``
这一层用法稳定；快照格式、路径安全校验与原子发布逻辑全部实现在 ``core`` 内。
"""

from .core import (
    ARCHIVE_NAME,
    FORMAT_NAME,
    FORMAT_VERSION,
    Issue,
    RestoreInfo,
    SnapshotInfo,
    SnapshotInputError,
    SnapshotOperationError,
    VerificationError,
    create_snapshot,
    restore_archive,
    verify_archive,
)

# 对外稳定 API 清单：与上面的导入一一对应，新增或删除导出时两处需同步维护。
__all__ = [
    "ARCHIVE_NAME",
    "FORMAT_NAME",
    "FORMAT_VERSION",
    "Issue",
    "RestoreInfo",
    "SnapshotInfo",
    "SnapshotInputError",
    "SnapshotOperationError",
    "VerificationError",
    "create_snapshot",
    "restore_archive",
    "verify_archive",
]

# 包版本号，CLI 的 --version 输出该值；发布时需与打包元数据保持一致。
__version__ = "0.1.0"
