"""vault-snapshot 命令行界面。

定义 ``create`` / ``verify`` / ``restore`` 三个子命令及各自的必填路径参数，
把 ``vault_snapshot.core`` 抛出的异常翻译成稳定的退出码与可读错误信息，
使脚本化调用无需解析 traceback：成功为 0，校验或发布失败为 1，路径与用法
错误为 2（argparse 自身的用法错误同样以 2 退出）。

所有路径都必须显式给出，CLI 不提供任何默认 Vault 或默认工作目录。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from . import __version__
from .core import (
    SnapshotInputError,
    SnapshotOperationError,
    VerificationError,
    create_snapshot,
    restore_archive,
    verify_archive,
)


def build_parser() -> argparse.ArgumentParser:
    """构造完整的参数解析器。

    三个子命令都以 ``required=True`` 注册且路径参数全部必填：缺少子命令或缺少
    ``--vault`` / ``--work-dir`` / ``--archive`` / ``--dest`` 时由 argparse 直接
    打印用法并以退出码 2 结束进程，不进入业务函数。

    Returns:
        注册完毕的 ``argparse.ArgumentParser``；``parse_args`` 产出的命名
        空间带 ``command`` 字段，取值为 ``create`` / ``verify`` / ``restore``。
    """
    parser = argparse.ArgumentParser(
        prog="vault-snapshot",
        description=(
            "Create, verify, and restore local Vault snapshots. "
            "All paths are explicit; there are no home-directory or temp-dir defaults."
        ),
    )
    parser.add_argument(
        "--version", action="version", version="%(prog)s " + __version__
    )

    commands = parser.add_subparsers(dest="command", required=True)

    create_parser = commands.add_parser(
        "create",
        help="create vault-snapshot.zip inside an explicit work directory",
        description=(
            "Scan the explicit vault, build a complete ZIP, verify it, and "
            "atomically publish it as WORK_DIR/vault-snapshot.zip without "
            "overwriting an existing path."
        ),
    )
    create_parser.add_argument(
        "--vault",
        required=True,
        type=Path,
        metavar="PATH",
        help="vault directory to snapshot",
    )
    create_parser.add_argument(
        "--work-dir",
        required=True,
        type=Path,
        metavar="PATH",
        help=(
            "existing directory outside the vault for temporary files and the "
            "published vault-snapshot.zip"
        ),
    )

    verify_parser = commands.add_parser(
        "verify",
        help="verify an archive without modifying anything",
        description=(
            "Check the archive structure, manifest, path safety, member sizes, "
            "and SHA-256 digests."
        ),
    )
    verify_parser.add_argument(
        "--archive", required=True, type=Path, metavar="PATH", help="ZIP to verify"
    )

    restore_parser = commands.add_parser(
        "restore",
        help="restore an archive into a brand-new directory",
        description=(
            "Verify archive structure and write into a fresh destination. "
            "The destination is published without overwriting existing data; "
            "an existing file or directory is never merged, replaced, or removed."
        ),
    )
    restore_parser.add_argument(
        "--archive", required=True, type=Path, metavar="PATH", help="ZIP to restore"
    )
    restore_parser.add_argument(
        "--dest",
        required=True,
        type=Path,
        metavar="PATH",
        help="destination path that must not exist",
    )

    return parser


def _print_verification_failure(error: VerificationError) -> None:
    """把校验问题逐条输出到标准错误。

    问题列表已在异常构造时去重排序，这里只负责排版：数量写在首行，随后每条
    以 ``kind: detail`` 缩进两格，便于在长日志里按 kind（``MISSING``、
    ``TAMPERED``、``UNSAFE_PATH`` 等）过滤。

    Args:
        error: 携带问题元组的校验异常。
    """
    print(
        f"error: archive verification failed ({len(error.issues)} issue(s)):",
        file=sys.stderr,
    )
    for issue in error.issues:
        print(f"  {issue.kind}: {issue.detail}", file=sys.stderr)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """解析参数、执行单个子命令并返回进程退出码。

    成功路径把结果的三项摘要（路径、文件数、字节数）写到标准输出，失败路径
    只把错误写到标准错误，便于调用方用重定向区分。

    Args:
        argv: 参数序列；为 ``None`` 时由 argparse 读取 ``sys.argv[1:]``，测试
            可直接传入列表以隔离真实命令行。

    Returns:
        0 表示成功；1 表示归档校验失败或发布失败（含未被包装成输入错误的
        ``OSError``）；2 表示输入非法（路径不存在、目标已存在、工作目录位于
        Vault 内、Vault 含符号链接或不可移植路径等）。

    Note:
        末尾的 ``parser.error`` 分支在正常解析流程中不可达（子命令为必需项），
        保留它是为了将来新增子命令时漏接分支也能明确失败而不是静默返回 0。
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "create":
            result = create_snapshot(args.vault, args.work_dir)
            print(f"Snapshot created: {result.archive}")
            print(f"Files: {result.file_count}")
            print(f"Bytes: {result.total_bytes}")
            return 0

        if args.command == "verify":
            result = verify_archive(args.archive)
            print(f"Snapshot verified: {result.archive}")
            print(f"Files: {result.file_count}")
            print(f"Bytes: {result.total_bytes}")
            return 0

        if args.command == "restore":
            result = restore_archive(args.archive, args.dest)
            print(f"Snapshot restored: {result.destination}")
            print(f"Files: {result.file_count}")
            print(f"Bytes: {result.total_bytes}")
            return 0

        parser.error(f"unknown command: {args.command}")
    except VerificationError as exc:
        _print_verification_failure(exc)
        return 1
    except SnapshotInputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (SnapshotOperationError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return 2
