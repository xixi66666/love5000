"""Offline, standard-library-only Vault snapshot tooling."""

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

__version__ = "0.1.0"
