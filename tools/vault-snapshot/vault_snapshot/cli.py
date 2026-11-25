"""Command-line interface for vault-snapshot."""

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
    print(
        f"error: archive verification failed ({len(error.issues)} issue(s)):",
        file=sys.stderr,
    )
    for issue in error.issues:
        print(f"  {issue.kind}: {issue.detail}", file=sys.stderr)


def main(argv: Optional[Sequence[str]] = None) -> int:
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
