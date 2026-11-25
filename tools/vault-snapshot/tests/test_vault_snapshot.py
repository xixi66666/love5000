from __future__ import annotations

import errno
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from typing import Dict, Iterable, Optional, Sequence, Tuple
from unittest import mock

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from vault_snapshot import core  # noqa: E402
from vault_snapshot.core import (  # noqa: E402
    Issue,
    SnapshotInputError,
    SnapshotOperationError,
    VerificationError,
    create_snapshot,
    restore_archive,
)

MANIFEST = "MANIFEST.json"
PAYLOAD_PREFIX = "files/"
FIXED_TIME = (1980, 1, 1, 0, 0, 0)


class VaultSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory(prefix="vault-snapshot-test-")
        self.addCleanup(self._temp.cleanup)
        self.root = Path(self._temp.name)
        self.vault = self.root / "vault"
        self.work = self.root / "work"
        self.restore_parent = self.root / "restore-parent"
        self.vault.mkdir()
        self.work.mkdir()
        self.restore_parent.mkdir()

    def write_vault(self, files: Dict[str, bytes]) -> None:
        for relative, content in files.items():
            target = self.vault.joinpath(*relative.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)

    def sample_files(self) -> Dict[str, bytes]:
        return {
            "notes/alpha.md": "# Alpha\n\nSynthetic note.\n".encode("utf-8"),
            "notes/empty.md": b"",
            "notes/nested/deep.md": b"- [ ] offline restore drill\n",
            "笔记/索引.md": "# 个人索引\n".encode("utf-8"),
            "attachments/pixel.png": b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 2,
        }

    def run_cli(self, *args: object) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        env["PYTHONUTF8"] = "1"
        return subprocess.run(
            [sys.executable, "-m", "vault_snapshot", *[str(arg) for arg in args]],
            cwd=str(TOOL_ROOT),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def create_archive(self) -> Path:
        result = self.run_cli(
            "create", "--vault", self.vault, "--work-dir", self.work
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        archive = self.work / "vault-snapshot.zip"
        self.assertTrue(archive.is_file())
        return archive

    def assert_no_create_temp(self) -> None:
        leftovers = [
            path.name
            for path in self.work.iterdir()
            if path.name.startswith(".vault-snapshot-")
        ]
        self.assertEqual(leftovers, [])

    def assert_no_restore_stage(self) -> None:
        leftovers = [
            path.name
            for path in self.restore_parent.iterdir()
            if path.name.startswith(".vault-snapshot-restore-")
        ]
        self.assertEqual(leftovers, [])

    def read_manifest(self, archive: Path) -> dict:
        with zipfile.ZipFile(archive) as zf:
            return json.loads(zf.read(MANIFEST).decode("utf-8"))

    def test_cli_create_verify_restore_round_trip(self) -> None:
        files = self.sample_files()
        self.write_vault(files)
        archive = self.create_archive()

        with zipfile.ZipFile(archive) as zf:
            names = zf.namelist()
            infos = zf.infolist()

        expected_members = [
            PAYLOAD_PREFIX + path for path in sorted(files)
        ] + [MANIFEST]
        self.assertEqual(names, expected_members)
        self.assertEqual({info.date_time for info in infos}, {FIXED_TIME})

        manifest = self.read_manifest(archive)
        self.assertEqual(manifest["format"], "vault-snapshot")
        self.assertEqual(manifest["version"], 1)
        self.assertEqual(
            [entry["path"] for entry in manifest["files"]], sorted(files)
        )
        for entry in manifest["files"]:
            content = files[entry["path"]]
            self.assertEqual(entry["size"], len(content))
            self.assertEqual(entry["sha256"], hashlib.sha256(content).hexdigest())

        verify = self.run_cli("verify", "--archive", archive)
        self.assertEqual(verify.returncode, 0, verify.stderr)
        self.assertIn("Snapshot verified", verify.stdout)

        destination = self.restore_parent / "restored"
        restore = self.run_cli(
            "restore", "--archive", archive, "--dest", destination
        )
        self.assertEqual(restore.returncode, 0, restore.stderr)
        self.assertTrue(destination.is_dir())
        restored = {
            path.relative_to(destination).as_posix(): path.read_bytes()
            for path in destination.rglob("*")
            if path.is_file()
        }
        self.assertEqual(restored, files)
        self.assert_no_restore_stage()
        self.assert_no_create_temp()

    def test_create_is_deterministic_for_identical_content(self) -> None:
        self.write_vault(self.sample_files())
        archive_one = self.create_archive()
        first = archive_one.read_bytes()

        work_two = self.root / "work-two"
        work_two.mkdir()
        second_result = self.run_cli(
            "create", "--vault", self.vault, "--work-dir", work_two
        )
        self.assertEqual(second_result.returncode, 0, second_result.stderr)
        second = (work_two / "vault-snapshot.zip").read_bytes()

        self.assertEqual(first, second)
        self.assertEqual(
            [entry["path"] for entry in self.read_manifest(archive_one)["files"]],
            sorted(self.sample_files()),
        )

    def test_empty_vault_round_trip(self) -> None:
        archive = self.create_archive()
        manifest = self.read_manifest(archive)
        self.assertEqual(manifest["files"], [])

        destination = self.restore_parent / "empty-restored"
        restore = self.run_cli(
            "restore", "--archive", archive, "--dest", destination
        )
        self.assertEqual(restore.returncode, 0, restore.stderr)
        self.assertEqual(list(destination.iterdir()), [])
        self.assert_no_restore_stage()

    def test_create_refuses_existing_archive_then_recovers(self) -> None:
        self.write_vault(self.sample_files())
        archive = self.create_archive()
        original = archive.read_bytes()

        refused = self.run_cli(
            "create", "--vault", self.vault, "--work-dir", self.work
        )
        self.assertEqual(refused.returncode, 2)
        self.assertIn("already exists", refused.stderr)
        self.assertEqual(archive.read_bytes(), original)
        self.assert_no_create_temp()

        archive.unlink()
        recovered = self.run_cli(
            "create", "--vault", self.vault, "--work-dir", self.work
        )
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        self.assertTrue(archive.is_file())
        self.assert_no_create_temp()

    def test_create_refuses_preexisting_empty_directory(self) -> None:
        self.write_vault({"note.md": b"# note\n"})
        archive = self.work / "vault-snapshot.zip"
        archive.mkdir()

        result = self.run_cli(
            "create", "--vault", self.vault, "--work-dir", self.work
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("already exists", result.stderr)
        self.assertTrue(archive.is_dir())
        self.assertEqual(list(archive.iterdir()), [])
        self.assert_no_create_temp()

    def test_create_race_with_file_is_not_overwritten(self) -> None:
        self.write_vault({"note.md": b"# note\n"})
        archive = self.work / "vault-snapshot.zip"
        peer = b"created by another process\n"
        real_verify = core.verify_archive

        def verify_then_create_peer(path: Path) -> core.SnapshotInfo:
            result = real_verify(path)
            archive.write_bytes(peer)
            return result

        with mock.patch.object(
            core, "verify_archive", side_effect=verify_then_create_peer
        ):
            with self.assertRaises(SnapshotOperationError) as raised:
                create_snapshot(self.vault, self.work)

        self.assertIn("refusing to overwrite", str(raised.exception))
        self.assertEqual(archive.read_bytes(), peer)
        self.assert_no_create_temp()

        archive.unlink()
        recovered = create_snapshot(self.vault, self.work)
        self.assertTrue(recovered.archive.is_file())
        self.assert_no_create_temp()

    def test_create_race_with_empty_directory_is_not_overwritten(self) -> None:
        self.write_vault({"note.md": b"# note\n"})
        archive = self.work / "vault-snapshot.zip"
        real_verify = core.verify_archive

        def verify_then_create_directory(path: Path) -> core.SnapshotInfo:
            result = real_verify(path)
            archive.mkdir()
            return result

        with mock.patch.object(
            core, "verify_archive", side_effect=verify_then_create_directory
        ):
            with self.assertRaises(SnapshotOperationError) as raised:
                create_snapshot(self.vault, self.work)

        self.assertIn("refusing to overwrite", str(raised.exception))
        self.assertTrue(archive.is_dir())
        self.assertEqual(list(archive.iterdir()), [])
        self.assert_no_create_temp()

    def test_create_reports_unsupported_atomic_publish(self) -> None:
        self.write_vault({"note.md": b"# note\n"})
        archive = self.work / "vault-snapshot.zip"
        unavailable = OSError(errno.EOPNOTSUPP, "operation not supported")
        primitive = "rename" if os.name == "nt" else "link"

        with mock.patch.object(core.os, primitive, side_effect=unavailable):
            with self.assertRaises(SnapshotOperationError) as raised:
                create_snapshot(self.vault, self.work)

        self.assertIn("without overwriting", str(raised.exception))
        self.assertFalse(archive.exists())
        self.assert_no_create_temp()

    def test_create_verifies_before_atomic_publish_and_can_retry(self) -> None:
        self.write_vault({"note.md": b"# note\n"})
        archive = self.work / "vault-snapshot.zip"

        with mock.patch.object(
            core,
            "verify_archive",
            side_effect=VerificationError([Issue("TEST", "forced verification failure")]),
        ):
            with self.assertRaises(VerificationError):
                create_snapshot(self.vault, self.work)

        self.assertFalse(archive.exists())
        self.assert_no_create_temp()

        result = create_snapshot(self.vault, self.work)
        self.assertTrue(result.archive.is_file())
        self.assertEqual(result.file_count, 1)
        self.assert_no_create_temp()

    def test_create_rejects_work_dir_inside_vault(self) -> None:
        self.write_vault({"note.md": b"# note\n"})
        inside = self.vault / "backup-work"
        inside.mkdir()

        result = self.run_cli(
            "create", "--vault", self.vault, "--work-dir", inside
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("outside the vault", result.stderr)
        self.assertFalse((inside / "vault-snapshot.zip").exists())

    def test_create_rejects_vault_symlink_and_recovers(self) -> None:
        self.write_vault({"note.md": b"# note\n"})
        target = self.root / "outside.md"
        target.write_text("# outside\n", encoding="utf-8")
        link = self.vault / "link.md"
        try:
            os.symlink(target, link)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlinks unavailable on this host: {exc}")

        refused = self.run_cli(
            "create", "--vault", self.vault, "--work-dir", self.work
        )
        self.assertEqual(refused.returncode, 2)
        self.assertIn("symbolic link", refused.stderr)
        self.assertFalse((self.work / "vault-snapshot.zip").exists())
        self.assert_no_create_temp()

        link.unlink()
        recovered = self.run_cli(
            "create", "--vault", self.vault, "--work-dir", self.work
        )
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        self.assert_no_create_temp()

    def test_cli_requires_explicit_vault_and_work_dir(self) -> None:
        missing_work = self.run_cli("create", "--vault", self.vault)
        self.assertEqual(missing_work.returncode, 2)
        self.assertIn("--work-dir", missing_work.stderr)

        missing_vault = self.run_cli("create", "--work-dir", self.work)
        self.assertEqual(missing_vault.returncode, 2)
        self.assertIn("--vault", missing_vault.stderr)

    def test_verify_and_restore_reject_corrupt_zip_cleanly(self) -> None:
        corrupt = self.root / "corrupt.zip"
        corrupt.write_bytes(b"this is not a zip archive")

        verify = self.run_cli("verify", "--archive", corrupt)
        self.assertEqual(verify.returncode, 1)
        self.assertIn("INVALID_ARCHIVE", verify.stderr)
        self.assertNotIn("Traceback", verify.stderr)

        destination = self.restore_parent / "corrupt-restore"
        restore = self.run_cli(
            "restore", "--archive", corrupt, "--dest", destination
        )
        self.assertEqual(restore.returncode, 1)
        self.assertIn("INVALID_ARCHIVE", restore.stderr)
        self.assertNotIn("Traceback", restore.stderr)
        self.assertFalse(destination.exists())
        self.assert_no_restore_stage()

    def test_verify_reports_missing_member(self) -> None:
        files = self.sample_files()
        self.write_vault(files)
        archive = self.create_archive()
        broken = self.root / "missing.zip"
        self.rewrite_archive(archive, broken, skip="files/notes/alpha.md")

        result = self.run_cli("verify", "--archive", broken)
        self.assertEqual(result.returncode, 1)
        self.assertIn("MISSING", result.stderr)
        self.assertIn("notes/alpha.md", result.stderr)

    def test_verify_reports_tampered_member_and_restore_cleans_up(self) -> None:
        files = self.sample_files()
        self.write_vault(files)
        archive = self.create_archive()
        broken = self.root / "tampered.zip"
        original = files["notes/alpha.md"]
        self.rewrite_archive(
            archive,
            broken,
            replace={"files/notes/alpha.md": b"X" * len(original)},
        )

        verify = self.run_cli("verify", "--archive", broken)
        self.assertEqual(verify.returncode, 1)
        self.assertIn("TAMPERED", verify.stderr)
        self.assertIn("notes/alpha.md", verify.stderr)

        destination = self.restore_parent / "tampered-restore"
        restore = self.run_cli(
            "restore", "--archive", broken, "--dest", destination
        )
        self.assertEqual(restore.returncode, 1)
        self.assertIn("TAMPERED", restore.stderr)
        self.assertFalse(destination.exists())
        self.assert_no_restore_stage()

        recovered = self.run_cli(
            "restore", "--archive", archive, "--dest", destination
        )
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        self.assertTrue(destination.is_dir())

    def test_restore_rejects_existing_destination_without_writing(self) -> None:
        self.write_vault(self.sample_files())
        archive = self.create_archive()
        destination = self.restore_parent / "existing"
        destination.mkdir()
        sentinel = destination / "keep.md"
        sentinel.write_text("keep\n", encoding="utf-8")

        result = self.run_cli(
            "restore", "--archive", archive, "--dest", destination
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("must not exist", result.stderr)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep\n")
        self.assertEqual(
            sorted(path.name for path in destination.iterdir()), ["keep.md"]
        )
        self.assert_no_restore_stage()

    def test_restore_rejects_existing_file(self) -> None:
        self.write_vault(self.sample_files())
        archive = self.create_archive()
        destination = self.restore_parent / "existing-file"
        peer = b"created before restore\n"
        destination.write_bytes(peer)

        result = self.run_cli(
            "restore", "--archive", archive, "--dest", destination
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("must not exist", result.stderr)
        self.assertEqual(destination.read_bytes(), peer)
        self.assert_no_restore_stage()

    def test_restore_rejects_existing_empty_directory(self) -> None:
        self.write_vault(self.sample_files())
        archive = self.create_archive()
        destination = self.restore_parent / "existing-empty"
        destination.mkdir()

        result = self.run_cli(
            "restore", "--archive", archive, "--dest", destination
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("must not exist", result.stderr)
        self.assertTrue(destination.is_dir())
        self.assertEqual(list(destination.iterdir()), [])
        self.assert_no_restore_stage()

    def test_restore_race_with_file_is_not_overwritten(self) -> None:
        self.write_vault(self.sample_files())
        archive = self.create_archive()
        destination = self.restore_parent / "raced-file"
        peer = b"created during restore\n"
        real_inspect = core._inspect_archive

        def inspect_then_create_peer(path: Path) -> core._Inspection:
            inspection = real_inspect(path)
            destination.write_bytes(peer)
            return inspection

        with mock.patch.object(
            core, "_inspect_archive", side_effect=inspect_then_create_peer
        ):
            with self.assertRaises(SnapshotOperationError) as raised:
                restore_archive(archive, destination)

        self.assertIn("refusing to overwrite", str(raised.exception))
        self.assertEqual(destination.read_bytes(), peer)
        self.assert_no_restore_stage()

        destination.unlink()
        recovered = restore_archive(archive, destination)
        self.assertEqual(recovered.file_count, len(self.sample_files()))
        self.assertEqual(
            (destination / "notes" / "alpha.md").read_bytes(),
            self.sample_files()["notes/alpha.md"],
        )
        self.assert_no_restore_stage()

    def test_restore_race_with_empty_directory_is_not_overwritten(self) -> None:
        self.write_vault(self.sample_files())
        archive = self.create_archive()
        destination = self.restore_parent / "raced-directory"
        real_inspect = core._inspect_archive

        def inspect_then_create_directory(path: Path) -> core._Inspection:
            inspection = real_inspect(path)
            destination.mkdir()
            return inspection

        with mock.patch.object(
            core, "_inspect_archive", side_effect=inspect_then_create_directory
        ):
            with self.assertRaises(SnapshotOperationError) as raised:
                restore_archive(archive, destination)

        self.assertIn("refusing to overwrite", str(raised.exception))
        self.assertTrue(destination.is_dir())
        self.assertEqual(list(destination.iterdir()), [])
        self.assert_no_restore_stage()

    def test_restore_reports_unsupported_atomic_publish(self) -> None:
        self.write_vault({"note.md": b"# note\n"})
        archive = self.create_archive()
        destination = self.restore_parent / "unsupported-publish"
        unavailable = OSError(errno.EOPNOTSUPP, "operation not supported")

        with mock.patch.object(core.os, "rename", side_effect=unavailable):
            with self.assertRaises(SnapshotOperationError) as raised:
                restore_archive(archive, destination)

        self.assertIn("without overwriting", str(raised.exception))
        self.assertFalse(destination.exists())
        self.assert_no_restore_stage()

    def test_reservation_cleanup_never_deletes_foreign_content(self) -> None:
        destination = self.restore_parent / "reserved-with-content"
        destination.mkdir()
        identity = core._directory_identity(destination)
        peer = destination / "peer.md"
        peer.write_text("peer\n", encoding="utf-8")

        core._remove_own_empty_reservation(destination, identity)

        self.assertTrue(destination.is_dir())
        self.assertEqual(peer.read_text(encoding="utf-8"), "peer\n")

    def test_windows_rename_retries_a_temporary_sharing_conflict(self) -> None:
        source = self.work / "staged"
        target = self.work / "published"
        locked = PermissionError("temporarily locked")
        locked.winerror = 5
        with mock.patch.object(core.os, "rename", side_effect=[locked, None]) as rename:
            with mock.patch.object(core.time, "sleep") as wait:
                core._rename_windows_no_replace(source, target)
        self.assertEqual(rename.call_args_list, [mock.call(source, target)] * 2)
        wait.assert_called_once()

    def test_reservation_cleanup_never_deletes_replaced_path(self) -> None:
        destination = self.restore_parent / "reserved-replaced"
        destination.mkdir()
        identity = core._directory_identity(destination)
        destination.rmdir()
        peer = b"replacement file\n"
        destination.write_bytes(peer)

        core._remove_own_empty_reservation(destination, identity)

        self.assertTrue(destination.is_file())
        self.assertEqual(destination.read_bytes(), peer)

    def test_reservation_cleanup_removes_own_empty_directory(self) -> None:
        destination = self.restore_parent / "reserved-empty"
        destination.mkdir()
        identity = core._directory_identity(destination)

        core._remove_own_empty_reservation(destination, identity)

        self.assertFalse(destination.exists())

    def test_restore_rejects_path_traversal_and_windows_aliases(self) -> None:
        malicious_members = [
            "files/../escaped.md",
            "files/.. /escaped.md",
            "files/CON.md",
            "files/bad?.md",
        ]
        for index, member in enumerate(malicious_members):
            with self.subTest(member=member):
                archive = self.root / f"traversal-{index}.zip"
                self.write_test_zip(
                    archive,
                    payloads=[(member, b"escape\n", _file_mode())],
                    manifest=self.manifest_for([]),
                )

                destination = self.restore_parent / f"traversal-restore-{index}"
                result = self.run_cli(
                    "restore", "--archive", archive, "--dest", destination
                )
                self.assertEqual(result.returncode, 1)
                self.assertIn("UNSAFE_PATH", result.stderr)
                self.assertFalse(destination.exists())
                self.assertFalse((self.restore_parent / "escaped.md").exists())
                self.assert_no_restore_stage()

    def test_restore_rejects_manifest_path_traversal(self) -> None:
        content = b"# safe payload\n"
        archive = self.root / "manifest-traversal.zip"
        manifest = {
            "format": "vault-snapshot",
            "version": 1,
            "files": [
                {
                    "path": "../escaped.md",
                    "size": len(content),
                    "sha256": hashlib.sha256(content).hexdigest(),
                }
            ],
        }
        self.write_test_zip(
            archive,
            payloads=[("files/safe.md", content, _file_mode())],
            manifest=manifest,
        )

        destination = self.restore_parent / "manifest-traversal-restore"
        result = self.run_cli(
            "restore", "--archive", archive, "--dest", destination
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("INVALID_MANIFEST", result.stderr)
        self.assertFalse(destination.exists())
        self.assertFalse((self.restore_parent / "escaped.md").exists())
        self.assert_no_restore_stage()

    def test_restore_rejects_duplicate_zip_members(self) -> None:
        content = b"# duplicate\n"
        archive = self.root / "duplicate.zip"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.write_test_zip(
                archive,
                payloads=[
                    ("files/notes/duplicate.md", content, _file_mode()),
                    ("files/notes/duplicate.md", content, _file_mode()),
                ],
                manifest=self.manifest_for([("notes/duplicate.md", content)]),
            )

        destination = self.restore_parent / "duplicate-restore"
        result = self.run_cli(
            "restore", "--archive", archive, "--dest", destination
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("DUPLICATE_MEMBER", result.stderr)
        self.assertFalse(destination.exists())
        self.assert_no_restore_stage()

    def test_restore_rejects_symlink_member(self) -> None:
        archive = self.root / "symlink.zip"
        symlink_mode = (stat.S_IFLNK | 0o777) << 16
        self.write_test_zip(
            archive,
            payloads=[
                ("files/notes/link.md", b"../../outside.md", symlink_mode)
            ],
            manifest=self.manifest_for([("notes/link.md", b"")]),
        )

        destination = self.restore_parent / "symlink-restore"
        result = self.run_cli(
            "restore", "--archive", archive, "--dest", destination
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("SYMLINK", result.stderr)
        self.assertFalse(destination.exists())
        self.assert_no_restore_stage()

    def test_restore_rejects_windows_case_collisions(self) -> None:
        payloads_and_files = [
            ("files/Notes/A.md", b"# A\n", _file_mode()),
            ("files/notes/a.md", b"# a\n", _file_mode()),
        ]
        files = [
            ("Notes/A.md", b"# A\n"),
            ("notes/a.md", b"# a\n"),
        ]
        manifest = self.manifest_for(files)
        # Python's code-point sort already places "Notes" before "notes".
        self.assertEqual(
            [entry["path"] for entry in manifest["files"]],
            ["Notes/A.md", "notes/a.md"],
        )

        for label in ("file", "directory"):
            with self.subTest(label=label):
                archive = self.root / f"case-{label}.zip"
                if label == "file":
                    payloads = payloads_and_files
                    selected_manifest = manifest
                else:
                    dir_payloads = [
                        ("files/Folder/one.md", b"# one\n", _file_mode()),
                        ("files/folder/two.md", b"# two\n", _file_mode()),
                    ]
                    dir_files = [
                        ("Folder/one.md", b"# one\n"),
                        ("folder/two.md", b"# two\n"),
                    ]
                    payloads = dir_payloads
                    selected_manifest = self.manifest_for(dir_files)

                self.write_test_zip(
                    archive, payloads=payloads, manifest=selected_manifest
                )
                destination = self.restore_parent / f"case-{label}-restore"
                result = self.run_cli(
                    "restore", "--archive", archive, "--dest", destination
                )
                self.assertEqual(result.returncode, 1)
                self.assertIn("CASE_COLLISION", result.stderr)
                self.assertFalse(destination.exists())
                self.assert_no_restore_stage()

    def test_verify_rejects_untracked_member_and_bad_manifest(self) -> None:
        content = b"# note\n"
        untracked = self.root / "untracked.zip"
        self.write_test_zip(
            untracked,
            payloads=[
                ("files/note.md", content, _file_mode()),
                ("files/extra.md", b"extra\n", _file_mode()),
            ],
            manifest=self.manifest_for([("note.md", content)]),
        )
        result = self.run_cli("verify", "--archive", untracked)
        self.assertEqual(result.returncode, 1)
        self.assertIn("UNEXPECTED", result.stderr)
        self.assertIn("extra.md", result.stderr)

        invalid = self.root / "invalid-manifest.zip"
        self.write_test_zip(
            invalid,
            payloads=[("files/notes/note.md", content, _file_mode())],
            manifest={"format": "not-a-vault-snapshot", "version": 1, "files": []},
        )
        invalid_result = self.run_cli("verify", "--archive", invalid)
        self.assertEqual(invalid_result.returncode, 1)
        self.assertIn("INVALID_MANIFEST", invalid_result.stderr)

    # -- helpers ---------------------------------------------------------

    def rewrite_archive(
        self,
        source: Path,
        destination: Path,
        skip: str = "",
        replace: Optional[Dict[str, bytes]] = None,
    ) -> None:
        replace = replace or {}
        with zipfile.ZipFile(source, "r") as zin, zipfile.ZipFile(
            destination, "w"
        ) as zout:
            for info in zin.infolist():
                if info.filename == skip:
                    continue
                data = replace.get(info.filename, zin.read(info))
                zout.writestr(info, data)

    def write_test_zip(
        self,
        path: Path,
        payloads: Sequence[Tuple[str, bytes, int]],
        manifest: dict,
    ) -> None:
        manifest_bytes = (
            json.dumps(
                manifest,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
        with zipfile.ZipFile(
            path, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True
        ) as zf:
            for name, data, external_attr in payloads:
                info = zipfile.ZipInfo(name, date_time=FIXED_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = external_attr
                zf.writestr(info, data)
            zf.writestr(_file_zip_info(MANIFEST), manifest_bytes)

    def manifest_for(self, files: Iterable[Tuple[str, bytes]]) -> dict:
        ordered = sorted(files, key=lambda item: item[0])
        return {
            "format": "vault-snapshot",
            "version": 1,
            "files": [
                {
                    "path": relative,
                    "size": len(content),
                    "sha256": hashlib.sha256(content).hexdigest(),
                }
                for relative, content in ordered
            ],
        }


def _file_mode() -> int:
    return (stat.S_IFREG | 0o644) << 16


def _file_zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=FIXED_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = _file_mode()
    return info


if __name__ == "__main__":
    unittest.main()
