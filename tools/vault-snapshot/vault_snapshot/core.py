"""Create, verify, and restore self-contained Vault snapshot archives.

The archive format is intentionally small and dependency-free:

    MANIFEST.json
    files/<relative path>

The manifest lists every regular file with its portable relative path, byte
size, and SHA-256 digest.  Both the manifest and the payload entries are
written in a deterministic order with fixed ZIP metadata.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import time
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

FORMAT_NAME = "vault-snapshot"
FORMAT_VERSION = 1
MANIFEST_NAME = "MANIFEST.json"
PAYLOAD_PREFIX = "files/"
ARCHIVE_NAME = "vault-snapshot.zip"
_CHUNK_SIZE = 1024 * 1024
_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_WINDOWS_RESERVED_STEMS = frozenset(
    {
        "con",
        "prn",
        "aux",
        "nul",
        "clock$",
        "conin$",
        "conout$",
        *(f"com{number}" for number in range(1, 10)),
        *(f"lpt{number}" for number in range(1, 10)),
    }
)


class SnapshotInputError(Exception):
    """The paths or command inputs are invalid; nothing was published."""


class SnapshotOperationError(Exception):
    """A snapshot operation could not be completed safely."""


class VerificationError(SnapshotOperationError):
    """An archive failed structural or integrity verification."""

    def __init__(self, issues: Sequence["Issue"]):
        self.issues = _unique_issues(issues)
        super().__init__(f"{len(self.issues)} verification issue(s)")


@dataclass(frozen=True, order=True)
class Issue:
    kind: str
    detail: str


@dataclass(frozen=True)
class ManifestEntry:
    path: str
    size: int
    sha256: str


@dataclass(frozen=True)
class SnapshotManifest:
    files: Tuple[ManifestEntry, ...]


@dataclass(frozen=True)
class SnapshotInfo:
    archive: Path
    file_count: int
    total_bytes: int


@dataclass(frozen=True)
class RestoreInfo:
    destination: Path
    file_count: int
    total_bytes: int


@dataclass(frozen=True)
class _Inspection:
    manifest: SnapshotManifest
    payload_infos: Dict[str, zipfile.ZipInfo]


def create_snapshot(vault: Path, work_dir: Path) -> SnapshotInfo:
    """Build and atomically publish WORK_DIR/vault-snapshot.zip.

    The temporary archive is created inside the explicit work directory,
    fully verified, and only then published with a platform primitive that
    cannot replace an existing file or empty directory.
    """

    vault_path = Path(vault)
    work_path = Path(work_dir)

    if not vault_path.is_dir():
        raise SnapshotInputError(f"vault is not an existing directory: {vault_path}")
    try:
        vault_root = vault_path.resolve(strict=True)
    except OSError as exc:
        raise SnapshotInputError(f"cannot resolve vault {vault_path}: {exc}") from exc

    if not work_path.is_dir():
        raise SnapshotInputError(
            f"work directory is not an existing directory: {work_path}"
        )
    try:
        work_root = work_path.resolve(strict=True)
    except OSError as exc:
        raise SnapshotInputError(
            f"cannot resolve work directory {work_path}: {exc}"
        ) from exc

    if _is_within(work_root, vault_root):
        raise SnapshotInputError("work directory must be outside the vault")

    archive = work_root / ARCHIVE_NAME
    if os.path.lexists(archive):
        raise SnapshotInputError(
            f"archive already exists; move or remove it first: {archive}"
        )

    relative_paths = _scan_vault(vault_root)
    total_bytes = 0

    fd, temp_name = tempfile.mkstemp(
        prefix=".vault-snapshot-", suffix=".zip.tmp", dir=str(work_root)
    )
    os.close(fd)
    temp_path: Optional[Path] = Path(temp_name)

    try:
        entries, total_bytes = _write_archive(temp_path, vault_root, relative_paths)
        verify_archive(temp_path)
        _publish_file_no_replace(temp_path, archive)
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass

    return SnapshotInfo(
        archive=archive,
        file_count=len(entries),
        total_bytes=total_bytes,
    )


def verify_archive(archive: Path) -> SnapshotInfo:
    """Verify an archive without modifying it."""

    archive_path = _require_archive(archive)
    inspection = _inspect_archive(archive_path)
    issues = _check_payload_hashes(archive_path, inspection)
    if issues:
        raise VerificationError(issues)

    return SnapshotInfo(
        archive=archive_path,
        file_count=len(inspection.manifest.files),
        total_bytes=sum(entry.size for entry in inspection.manifest.files),
    )


def restore_archive(archive: Path, destination: Path) -> RestoreInfo:
    """Restore an archive into a brand-new directory.

    The output is assembled in a sibling staging directory.  It is published
    only after every file has been written and hashed, using a primitive that
    cannot replace a concurrently created file or directory.  On any failure
    the staging directory is removed; a POSIX destination reservation is
    removed only when it is verifiably still the empty directory this call
    created.
    """

    archive_path = _require_archive(archive)
    destination = Path(destination)
    parent = destination.parent

    if not parent.is_dir():
        raise SnapshotInputError(
            f"destination parent is not an existing directory: {parent}"
        )
    if os.path.lexists(destination):
        raise SnapshotInputError(
            f"destination must not exist (including broken links): {destination}"
        )

    inspection = _inspect_archive(archive_path)
    stage = Path(
        tempfile.mkdtemp(
            prefix=".vault-snapshot-restore-", dir=str(parent)
        )
    )
    published = False
    total_bytes = 0

    try:
        try:
            zf_context = zipfile.ZipFile(archive_path, "r")
        except (zipfile.BadZipFile, EOFError, NotImplementedError, ValueError) as exc:
            raise VerificationError(
                [Issue("INVALID_ARCHIVE", f"archive cannot be reopened: {exc}")]
            ) from exc

        with zf_context as zf:
            for entry in inspection.manifest.files:
                info = inspection.payload_infos[entry.path]
                target = stage.joinpath(*entry.path.split("/"))
                target.parent.mkdir(parents=True, exist_ok=True)

                digest = hashlib.sha256()
                actual_size = 0
                try:
                    with zf.open(info, "r") as source, open(target, "xb") as out:
                        while True:
                            chunk = source.read(_CHUNK_SIZE)
                            if not chunk:
                                break
                            digest.update(chunk)
                            actual_size += len(chunk)
                            out.write(chunk)
                except (
                    zipfile.BadZipFile,
                    RuntimeError,
                    EOFError,
                    NotImplementedError,
                    ValueError,
                    zlib.error,
                ) as exc:
                    raise VerificationError(
                        [
                            Issue(
                                "TAMPERED",
                                f'"{entry.path}": cannot be decompressed: {exc}',
                            )
                        ]
                    ) from exc

                if actual_size != entry.size or digest.hexdigest() != entry.sha256:
                    raise VerificationError(
                        [
                            Issue(
                                "TAMPERED",
                                f'"{entry.path}": content does not match the manifest',
                            )
                        ]
                    )
                total_bytes += actual_size

        _publish_directory_no_replace(stage, destination)
        published = True
    finally:
        if not published:
            shutil.rmtree(stage, ignore_errors=True)

    return RestoreInfo(
        destination=destination,
        file_count=len(inspection.manifest.files),
        total_bytes=total_bytes,
    )


def _require_archive(archive: Path) -> Path:
    archive_path = Path(archive)
    if not archive_path.is_file():
        raise SnapshotInputError(f"archive is not an existing file: {archive_path}")
    return archive_path


def _rename_windows_no_replace(source: Path, target: Path) -> None:
    """Retry brief Windows sharing conflicts while keeping rename's no-replace guarantee."""
    for delay in (0.05, 0.15, 0.30, None):
        try:
            os.rename(source, target)
            return
        except OSError as exc:
            if os.path.lexists(target) or isinstance(exc, FileExistsError):
                raise FileExistsError(str(target)) from exc
            if delay is None or getattr(exc, "winerror", None) not in (5, 32, 33):
                raise
            time.sleep(delay)


def _publish_file_no_replace(source: Path, target: Path) -> None:
    """Atomically create TARGET from SOURCE, refusing to replace anything.

    Windows ``os.rename`` is atomic and fails when the destination exists.
    POSIX ``os.rename`` may replace the destination, so a same-directory hard
    link is used instead: ``link`` is atomic and fails with ``EEXIST`` when
    TARGET already exists.  A hard link leaves SOURCE as a second name; the
    caller removes it in its cleanup block.

    An unsupported primitive is reported instead of falling back to an
    overwriting rename.
    """

    if os.name == "nt":
        try:
            _rename_windows_no_replace(source, target)
        except FileExistsError as exc:
            raise SnapshotOperationError(
                f"archive appeared while creating snapshot; refusing to "
                f"overwrite: {target}"
            ) from exc
        except OSError as exc:
            raise SnapshotOperationError(
                f"cannot publish archive atomically without overwriting on "
                f"this filesystem: {target}: {exc}"
            ) from exc
        return

    try:
        os.link(source, target)
    except FileExistsError as exc:
        raise SnapshotOperationError(
            f"archive appeared while creating snapshot; refusing to overwrite: "
            f"{target}"
        ) from exc
    except OSError as exc:
        raise SnapshotOperationError(
            f"cannot publish archive atomically without overwriting on this "
            f"filesystem: {target}: {exc}"
        ) from exc


def _publish_directory_no_replace(stage: Path, destination: Path) -> None:
    """Publish STAGE at DESTINATION without replacing an existing path.

    Windows directory rename is atomic and refuses to replace an existing
    file or directory.  POSIX rename can replace an existing empty directory,
    so the destination is first claimed with an exclusive ``os.mkdir``.
    That reservation is then verified by device/inode identity and emptiness
    immediately before the fully verified staging tree is atomically renamed
    over it.  A concurrent writer cannot make ``mkdir`` succeed twice, and
    content placed in the reservation makes the final rename fail.

    If the reservation was replaced or is no longer empty, it is left
    untouched.  Failure cleanup removes only an empty directory that still
    has the exact identity created here.
    """

    if os.name == "nt":
        try:
            _rename_windows_no_replace(stage, destination)
        except FileExistsError as exc:
            raise _destination_conflict(destination) from exc
        except OSError as exc:
            raise _directory_publish_error(destination, exc) from exc
        return

    try:
        os.mkdir(destination, 0o700)
    except FileExistsError as exc:
        raise _destination_conflict(destination) from exc
    except OSError as exc:
        raise SnapshotOperationError(
            f"cannot reserve destination exclusively: {destination}: {exc}"
        ) from exc

    reservation: Optional[Tuple[int, int]] = None
    published = False
    try:
        reservation = _directory_identity(destination)
        if not _directory_is_empty(destination):
            raise _destination_conflict(destination)

        try:
            # Replace only the empty reservation verified immediately above.
            os.rename(stage, destination)
        except OSError as exc:
            if not _reservation_matches(destination, reservation):
                raise _destination_conflict(destination) from exc
            if not _directory_is_empty(destination):
                raise _destination_conflict(destination) from exc
            raise _directory_publish_error(destination, exc) from exc
        published = True
    except SnapshotOperationError:
        raise
    except OSError as exc:
        raise _directory_publish_error(destination, exc) from exc
    finally:
        if not published:
            _remove_own_empty_reservation(destination, reservation)


def _destination_conflict(destination: Path) -> SnapshotOperationError:
    return SnapshotOperationError(
        f"destination appeared or changed during restore; refusing to "
        f"overwrite or remove it: {destination}"
    )


def _directory_publish_error(
    destination: Path, error: OSError
) -> SnapshotOperationError:
    return SnapshotOperationError(
        f"cannot publish restored directory atomically without overwriting on "
        f"this filesystem: {destination}: {error}"
    )


def _directory_identity(path: Path) -> Tuple[int, int]:
    info = os.lstat(path)
    if not stat.S_ISDIR(info.st_mode):
        raise _destination_conflict(path)
    return (info.st_dev, info.st_ino)


def _reservation_matches(path: Path, identity: Tuple[int, int]) -> bool:
    try:
        info = os.lstat(path)
    except OSError:
        return False
    return stat.S_ISDIR(info.st_mode) and (info.st_dev, info.st_ino) == identity


def _directory_is_empty(path: Path) -> bool:
    with os.scandir(path) as entries:
        return next(entries, None) is None


def _remove_own_empty_reservation(
    destination: Path, reservation: Optional[Tuple[int, int]]
) -> None:
    """Remove only the exact empty reservation created by this restore."""

    if reservation is None:
        return
    try:
        if not _reservation_matches(destination, reservation):
            return
        if not _directory_is_empty(destination):
            return
        os.rmdir(destination)
    except OSError:
        pass


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _scan_vault(vault_root: Path) -> List[str]:
    discovered: List[str] = []

    def walk(directory: Path, relative_dir: str) -> None:
        try:
            with os.scandir(directory) as iterator:
                entries = sorted(iterator, key=lambda item: item.name)
        except OSError as exc:
            label = relative_dir or "."
            raise SnapshotInputError(
                f"cannot read vault directory {label}: {exc}"
            ) from exc

        for entry in entries:
            relative = (
                f"{relative_dir}/{entry.name}" if relative_dir else entry.name
            )
            try:
                if entry.is_symlink():
                    raise SnapshotInputError(
                        f"vault contains a symbolic link, which is not supported: "
                        f"{relative}"
                    )
                if entry.is_dir(follow_symlinks=False):
                    walk(Path(entry.path), relative)
                elif entry.is_file(follow_symlinks=False):
                    discovered.append(relative)
                else:
                    raise SnapshotInputError(
                        f"vault contains a non-regular file, which is not supported: "
                        f"{relative}"
                    )
            except OSError as exc:
                raise SnapshotInputError(
                    f"cannot inspect vault entry {relative}: {exc}"
                ) from exc

    walk(vault_root, "")
    discovered.sort()

    for path in discovered:
        error = _path_error(path)
        if error:
            raise SnapshotInputError(f'vault path "{path}" is not portable: {error}')

    collisions = _collision_issues(discovered)
    if collisions:
        details = "; ".join(issue.detail for issue in collisions)
        raise SnapshotInputError(f"vault has unsafe path names: {details}")

    return discovered


def _path_error(path: str) -> Optional[str]:
    if not path:
        return "empty path"
    try:
        path.encode("utf-8")
    except UnicodeEncodeError:
        return "path is not valid UTF-8"
    if path.startswith("/"):
        return "absolute paths are not allowed"
    if "\\" in path:
        return "backslashes are not allowed"
    if any(char in ':\\<>"|?*' for char in path):
        return "Windows-invalid path characters are not allowed"
    if any(ord(char) < 32 or ord(char) == 127 for char in path):
        return "control characters are not allowed"

    for part in path.split("/"):
        if not part:
            return "empty path segments are not allowed"
        if part in (".", ".."):
            return "'.' and '..' path segments are not allowed"
        stripped = part.rstrip(" .")
        if not stripped:
            return "path segments may not end with a dot or space"
        if stripped != part:
            return "path segments may not end with a dot or space"
        stem = stripped.split(".", 1)[0].casefold()
        if stem in _WINDOWS_RESERVED_STEMS:
            return "Windows reserved device names are not allowed"
    return None


def _collision_issues(paths: Sequence[str]) -> List[Issue]:
    """Detect case-insensitive directory/file collisions casefold-style."""

    registry: Dict[str, Tuple[str, bool]] = {}
    issues: List[Issue] = []

    for path in paths:
        parts = path.split("/")
        for index in range(1, len(parts) + 1):
            prefix = "/".join(parts[:index])
            key = "/".join(part.casefold() for part in parts[:index])
            is_directory = index < len(parts)
            previous = registry.get(key)
            if previous is None:
                registry[key] = (prefix, is_directory)
                continue
            previous_path, previous_is_directory = previous
            if previous_path != prefix or previous_is_directory != is_directory:
                issues.append(
                    Issue(
                        "CASE_COLLISION",
                        f'"{previous_path}" and "{prefix}" collide on a '
                        "case-insensitive filesystem",
                    )
                )
    return issues


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=_ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    return info


def _manifest_bytes(entries: Sequence[ManifestEntry]) -> bytes:
    document = {
        "files": [
            {"path": entry.path, "sha256": entry.sha256, "size": entry.size}
            for entry in entries
        ],
        "format": FORMAT_NAME,
        "version": FORMAT_VERSION,
    }
    text = json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return (text + "\n").encode("utf-8")


def _write_archive(
    temp_path: Path, vault_root: Path, relative_paths: Sequence[str]
) -> Tuple[List[ManifestEntry], int]:
    entries: List[ManifestEntry] = []
    total_bytes = 0

    with zipfile.ZipFile(
        temp_path, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True
    ) as zf:
        for relative in relative_paths:
            source_path = vault_root.joinpath(*relative.split("/"))
            digest = hashlib.sha256()
            size = 0
            info = _zip_info(PAYLOAD_PREFIX + relative)

            try:
                source = open(source_path, "rb")
            except OSError as exc:
                raise SnapshotOperationError(
                    f"cannot read vault file {relative}: {exc}"
                ) from exc

            with source, zf.open(info, "w", force_zip64=True) as out:
                while True:
                    chunk = source.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    digest.update(chunk)
                    size += len(chunk)
                    out.write(chunk)

            entries.append(
                ManifestEntry(path=relative, size=size, sha256=digest.hexdigest())
            )
            total_bytes += size

        zf.writestr(_zip_info(MANIFEST_NAME), _manifest_bytes(entries))

    return entries, total_bytes


def _inspect_archive(archive_path: Path) -> _Inspection:
    try:
        with zipfile.ZipFile(archive_path, "r") as zf:
            infos = zf.infolist()
            issues, payload_infos, manifest_info = _inspect_members(infos)
            if issues:
                raise VerificationError(issues)
            if manifest_info is None:
                raise VerificationError(
                    [Issue("INVALID_ARCHIVE", f"missing {MANIFEST_NAME}")]
                )

            try:
                raw_manifest = zf.read(manifest_info)
            except (
                zipfile.BadZipFile,
                RuntimeError,
                EOFError,
                NotImplementedError,
                ValueError,
                OSError,
            ) as exc:
                raise VerificationError(
                    [Issue("TAMPERED", f"{MANIFEST_NAME} cannot be read: {exc}")]
                ) from exc

            manifest = _parse_manifest(raw_manifest)
            compare_issues = _compare_members(manifest, payload_infos)
            if compare_issues:
                raise VerificationError(compare_issues)
            return _Inspection(manifest=manifest, payload_infos=payload_infos)
    except (zipfile.BadZipFile, EOFError, NotImplementedError, ValueError) as exc:
        raise VerificationError(
            [Issue("INVALID_ARCHIVE", f"not a readable ZIP archive: {exc}")]
        ) from exc
    except OSError as exc:
        raise SnapshotInputError(f"cannot read archive {archive_path}: {exc}") from exc


def _inspect_members(
    infos: Sequence[zipfile.ZipInfo],
) -> Tuple[List[Issue], Dict[str, zipfile.ZipInfo], Optional[zipfile.ZipInfo]]:
    issues: List[Issue] = []
    payload_infos: Dict[str, zipfile.ZipInfo] = {}
    manifest_info: Optional[zipfile.ZipInfo] = None
    seen_names = set()

    for info in infos:
        name = info.filename
        if name in seen_names:
            issues.append(Issue("DUPLICATE_MEMBER", f'duplicate ZIP member "{name}"'))
            continue
        seen_names.add(name)

        mode = (info.external_attr >> 16) & 0xFFFF
        file_type = stat.S_IFMT(mode)

        if info.is_dir():
            issues.append(
                Issue("INVALID_ARCHIVE", f'directory entry is not allowed: "{name}"')
            )
            continue
        if file_type == stat.S_IFLNK:
            issues.append(
                Issue("SYMLINK", f'symbolic link entries are not allowed: "{name}"')
            )
            continue
        if file_type not in (0, stat.S_IFREG):
            issues.append(
                Issue("UNSUPPORTED_FILE_TYPE", f'non-regular ZIP entry: "{name}"')
            )
            continue
        if info.flag_bits & 0x1:
            issues.append(Issue("ENCRYPTED", f'encrypted ZIP entry: "{name}"'))
            continue

        if name == MANIFEST_NAME:
            manifest_info = info
            continue

        if name.startswith(PAYLOAD_PREFIX):
            relative = name[len(PAYLOAD_PREFIX) :]
            error = _path_error(relative)
            if error:
                issues.append(
                    Issue("UNSAFE_PATH", f'"{name}" is not a safe path: {error}')
                )
                continue
            payload_infos[relative] = info
            continue

        issues.append(
            Issue("UNEXPECTED_MEMBER", f'unknown archive member: "{name}"')
        )

    payload_paths = sorted(payload_infos)
    issues.extend(_collision_issues(payload_paths))
    if manifest_info is None:
        issues.append(Issue("INVALID_ARCHIVE", f"missing {MANIFEST_NAME}"))
    return _unique_issues(issues), payload_infos, manifest_info


def _parse_manifest(raw: bytes) -> SnapshotManifest:
    def invalid(detail: str) -> VerificationError:
        return VerificationError([Issue("INVALID_MANIFEST", detail)])

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise invalid(f"{MANIFEST_NAME} is not UTF-8: {exc}") from exc
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise invalid(f"{MANIFEST_NAME} is not valid JSON: {exc}") from exc

    if not isinstance(document, dict):
        raise invalid(f"{MANIFEST_NAME} must contain a JSON object")
    if set(document) != {"files", "format", "version"}:
        raise invalid(f"{MANIFEST_NAME} has unexpected or missing fields")
    if document["format"] != FORMAT_NAME:
        raise invalid(f"unsupported format: {document['format']!r}")
    if (
        type(document["version"]) is not int
        or document["version"] != FORMAT_VERSION
    ):
        raise invalid(f"unsupported format version: {document['version']!r}")

    raw_files = document["files"]
    if not isinstance(raw_files, list):
        raise invalid("'files' must be an array")

    entries: List[ManifestEntry] = []
    seen_paths = set()
    for index, raw_entry in enumerate(raw_files):
        where = f"files[{index}]"
        if not isinstance(raw_entry, dict):
            raise invalid(f"{where} must be an object")
        if set(raw_entry) != {"path", "sha256", "size"}:
            raise invalid(f"{where} has unexpected or missing fields")

        path = raw_entry["path"]
        size = raw_entry["size"]
        sha256 = raw_entry["sha256"]
        if not isinstance(path, str):
            raise invalid(f"{where}.path must be a string")
        error = _path_error(path)
        if error:
            raise invalid(f"{where}.path is unsafe: {error}")
        if type(size) is not int or size < 0:
            raise invalid(f"{where}.size must be a non-negative integer")
        if not isinstance(sha256, str) or not _SHA256_RE.fullmatch(sha256):
            raise invalid(f"{where}.sha256 must be 64 lowercase hex characters")
        if path in seen_paths:
            raise invalid(f"duplicate file entry: {path}")
        seen_paths.add(path)
        entries.append(ManifestEntry(path=path, size=size, sha256=sha256))

    paths = [entry.path for entry in entries]
    if paths != sorted(paths):
        raise VerificationError(
            [Issue("INVALID_MANIFEST", "file entries are not in deterministic order")]
        )

    collisions = _collision_issues(paths)
    if collisions:
        raise VerificationError(collisions)

    return SnapshotManifest(files=tuple(entries))


def _compare_members(
    manifest: SnapshotManifest,
    payload_infos: Dict[str, zipfile.ZipInfo],
) -> List[Issue]:
    issues: List[Issue] = []
    expected = {entry.path: entry for entry in manifest.files}
    actual = set(payload_infos)

    for entry in manifest.files:
        if entry.path not in actual:
            issues.append(
                Issue("MISSING", f'"{entry.path}" is listed in the manifest but absent')
            )

    for path in sorted(actual - set(expected)):
        issues.append(
            Issue("UNEXPECTED", f'"{path}" is present but absent from the manifest')
        )

    for entry in manifest.files:
        info = payload_infos.get(entry.path)
        if info is not None and info.file_size != entry.size:
            issues.append(
                Issue(
                    "TAMPERED",
                    f'"{entry.path}": archive size {info.file_size} does not match '
                    f"manifest size {entry.size}",
                )
            )

    return _unique_issues(issues)


def _check_payload_hashes(
    archive_path: Path, inspection: _Inspection
) -> List[Issue]:
    issues: List[Issue] = []

    try:
        with zipfile.ZipFile(archive_path, "r") as zf:
            for entry in inspection.manifest.files:
                info = inspection.payload_infos[entry.path]
                digest = hashlib.sha256()
                actual_size = 0
                try:
                    with zf.open(info, "r") as source:
                        while True:
                            chunk = source.read(_CHUNK_SIZE)
                            if not chunk:
                                break
                            digest.update(chunk)
                            actual_size += len(chunk)
                except (
                    zipfile.BadZipFile,
                    RuntimeError,
                    EOFError,
                    NotImplementedError,
                    ValueError,
                    zlib.error,
                ) as exc:
                    issues.append(
                        Issue(
                            "TAMPERED",
                            f'"{entry.path}": cannot be decompressed: {exc}',
                        )
                    )
                    continue

                actual_sha256 = digest.hexdigest()
                if actual_size != entry.size or actual_sha256 != entry.sha256:
                    issues.append(
                        Issue(
                            "TAMPERED",
                            f'"{entry.path}": size {actual_size} vs {entry.size}, '
                            f"sha256 {actual_sha256} vs {entry.sha256}",
                        )
                    )
    except (zipfile.BadZipFile, EOFError, NotImplementedError, ValueError) as exc:
        raise VerificationError(
            [Issue("INVALID_ARCHIVE", f"archive changed while reading: {exc}")]
        ) from exc
    except OSError as exc:
        raise SnapshotInputError(f"cannot read archive {archive_path}: {exc}") from exc

    return _unique_issues(issues)


def _unique_issues(issues: Sequence[Issue]) -> Tuple[Issue, ...]:
    return tuple(sorted(set(issues)))
