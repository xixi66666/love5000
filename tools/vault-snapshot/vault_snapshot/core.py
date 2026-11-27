"""创建、校验和恢复自包含的 Vault 快照归档。

归档结构刻意保持最小且无第三方依赖：

    MANIFEST.json
    files/<相对路径>

MANIFEST.json 逐条记录每个普通文件的便携相对路径、字节数和 SHA-256 摘要。
清单与负载条目都按固定顺序写入，并使用固定的 ZIP 元数据（1980-01-01、
ZIP_DEFLATED、固定权限位），因此同一份 Vault 内容在不同时间、不同目录重复
打包会得到逐字节相同的归档，便于比对、去重和离线演练。

三条不变量贯穿整个模块：

* 路径必须显式：不猜测 home、临时目录或默认 Vault，工作目录必须在 Vault
  之外，否则归档会被自身扫描收进快照。
* 永不覆盖：发布阶段只使用「目标已存在即失败」的原语——Windows 的
  ``os.rename``、POSIX 的同目录硬链接和独占 ``os.mkdir`` 占位；原语不可用时
  直接报错，绝不回退到可能覆盖的 rename。
* 先校验后发布：临时归档或暂存目录先完整写入并复核哈希，最后一步才原子
  地出现在目标位置；失败时只清理本次调用自己创建的临时物，不触碰他人数据。

对外入口只有 ``create_snapshot``、``verify_archive`` 和
``restore_archive`` 三个函数，其余以下划线开头。
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

# 归档格式指纹：MANIFEST.json 的 format / version 必须与此完全一致，否则校验
# 阶段以 INVALID_MANIFEST 拒绝，避免读写双方对同一字节流做出不同解释。
FORMAT_NAME = "vault-snapshot"
# 当前只支持版本 1；解析时要求该字段是 int（排除 True 这类布尔子类）。
FORMAT_VERSION = 1
# 清单在 ZIP 中的固定成员名，必须位于归档根目录。
MANIFEST_NAME = "MANIFEST.json"
# 负载成员统一前缀；清单里的 path 是去掉该前缀后的相对路径。
PAYLOAD_PREFIX = "files/"
# create 子命令在工作目录内固定产出的文件名。
ARCHIVE_NAME = "vault-snapshot.zip"
# 流式读写块大小（字节）；固定 1 MiB，使内存占用与文件总大小无关。
_CHUNK_SIZE = 1024 * 1024
# ZIP 条目时间戳取下限 1980-01-01，消除打包时刻对归档字节的影响。
_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
# 只接受 64 位小写十六进制摘要，避免大小写或长度差异导致比对假阴性。
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
# Windows 保留设备名；比较时只取路径首段并 casefold，因此 CON.md 这类带扩展
# 名的写法同样会被拒绝，恢复出来的文件才不会在 Windows 上无法创建。
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
    """入参或路径不合法；抛出时尚未发布任何产物。

    属于「改正参数即可重试」的错误：目录不存在、目标已存在、工作目录落在
    Vault 内、Vault 含符号链接或不可移植路径等。CLI 将其映射为退出码 2。
    """


class SnapshotOperationError(Exception):
    """操作无法在保证安全的前提下完成。

    典型场景是目标路径在发布瞬间被其他进程占据，或当前文件系统不提供「不覆盖
    的原子发布」原语。此时宁可失败也不降级为覆盖写入。CLI 映射为退出码 1。
    """


class VerificationError(SnapshotOperationError):
    """归档未通过结构或完整性校验。

    Args:
        issues: 具体问题序列；构造时去重并按 (kind, detail) 排序，保证同一
            归档重复校验得到完全相同的错误输出。
    """

    def __init__(self, issues: Sequence["Issue"]):
        """归一化问题列表，并生成只含问题数量的异常消息。

        Args:
            issues: 原始问题序列，允许重复；去重排序后再保存到 ``self.issues``，
                便于 CLI 稳定输出与测试断言。
        """
        self.issues = _unique_issues(issues)
        super().__init__(f"{len(self.issues)} verification issue(s)")


@dataclass(frozen=True, order=True)
class Issue:
    """单条校验问题。

    ``kind`` 是稳定的大写机器可读分类（如 ``MISSING``、``TAMPERED``、
    ``UNSAFE_PATH``），``detail`` 是面向人的说明。两者共同参与排序，因此问题
    输出顺序可复现。
    """

    kind: str
    detail: str


@dataclass(frozen=True)
class ManifestEntry:
    """清单中的单个文件条目，字段与 MANIFEST.json 的对象一一对应。"""

    # 相对 Vault 根的 POSIX 路径，使用 "/" 分隔且不带 "files/" 前缀。
    path: str
    # 未压缩字节数；校验阶段会与实际解压长度比对。
    size: int
    # 小写十六进制 SHA-256 摘要，共 64 个字符。
    sha256: str


@dataclass(frozen=True)
class SnapshotManifest:
    """解析后的清单。

    ``files`` 保持清单中的原始顺序；解析阶段已确认它按路径升序、无重复且无
    大小写冲突，因此后续比对可以直接依赖该顺序。
    """

    files: Tuple[ManifestEntry, ...]


@dataclass(frozen=True)
class SnapshotInfo:
    """create / verify 的结果摘要，供 CLI 打印。"""

    # 最终发布（或待校验）的归档路径。
    archive: Path
    # 归档内文件条目数，等于清单条目数。
    file_count: int
    # 全部负载文件的未压缩字节总数。
    total_bytes: int


@dataclass(frozen=True)
class RestoreInfo:
    """restore 的结果摘要。"""

    # 实际发布出来的目标目录。
    destination: Path
    # 写入的文件数。
    file_count: int
    # 写入的字节数，按解压后大小计。
    total_bytes: int


@dataclass(frozen=True)
class _Inspection:
    """一次归档结构解析的中间结果。

    把解析后的清单与 ZIP 成员句柄绑在一起，避免校验和恢复阶段重复打开、重复
    解析同一个归档。
    """

    manifest: SnapshotManifest
    # 相对路径 -> ZIP 成员元数据；键均已通过 _path_error 的安全校验。
    payload_infos: Dict[str, zipfile.ZipInfo]


def create_snapshot(vault: Path, work_dir: Path) -> SnapshotInfo:
    """创建快照并原子发布为 ``WORK_DIR/vault-snapshot.zip``。

    流程：解析并校验两个目录 → 递归扫描 Vault（拒绝符号链接、非常规文件和
    不可移植路径）→ 在工作目录内写临时归档 → 重新校验临时归档 → 用「目标已
    存在即失败」的原语发布。临时文件无论成功失败都会删除，因此失败后可以直接
    重试，不会残留半成品。

    Args:
        vault: 已存在的 Vault 目录；内部会 ``resolve(strict=True)`` 规范化，
            防止后续路径比较被相对路径或符号链接误导。
        work_dir: 已存在的工作目录，必须位于 Vault 之外；临时归档与最终
            归档都放在这里。之所以强制在外部，是因为归档若落在 Vault 内会被
            同一次或下一次扫描当成普通文件收录，导致快照包含自身。

    Returns:
        已发布归档的路径、文件条目数与未压缩字节总数。

    Raises:
        SnapshotInputError: 目录不存在或无法解析、工作目录在 Vault 内、目标
            归档已存在（含空目录与断链）、Vault 内含符号链接或非常规文件、
            路径不可移植或存在大小写冲突。
        SnapshotOperationError: 读取 Vault 文件失败，或当前文件系统无法在不
            覆盖的前提下原子发布。
        VerificationError: 临时归档自检失败；此时目标位置不会被创建。
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
    # lexists 连空目录与断链都算「已存在」，避免随后的原子发布覆盖它们。
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
    """只读校验归档，不修改任何文件。

    检查顺序：ZIP 是否可读、成员类型（拒绝目录条目、符号链接、加密成员和未知
    成员）、大小写冲突、清单字段与条目顺序、清单和成员是否一一对应，最后流式
    重算每个负载文件的 SHA-256。前几步只读元数据，因此结构非法时不必解压任何
    内容。

    Args:
        archive: 已存在的 ZIP 文件路径。

    Returns:
        校验通过时返回归档的文件条目数与未压缩字节总数。

    Raises:
        SnapshotInputError: 路径不是已存在的普通文件，或读取时发生 I/O 错误。
        VerificationError: 结构或摘要校验失败；异常内的 ``issues`` 是全部问题
            而非第一个问题。
    """

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
    """把归档恢复到一个全新的目录。

    先在 ``destination`` 的同级目录创建暂存目录（同盘才能原子 rename），逐文件
    写到暂存目录并边写边算 SHA-256，全部匹配后才把整个暂存树发布到目标位置；
    任何失败都会删除暂存目录，目标位置保持不存在。POSIX 上的目标占位只有在
    「仍是本次调用创建的那个空目录」时才被清理，绝不删除并发写入者的内容。

    Args:
        archive: 已存在的快照 ZIP；内部会重新解析并整份校验。
        destination: 目标目录，必须尚不存在（空目录、普通文件、符号链接或
            断链都视为已存在）；其父目录必须存在，暂存目录就创建在父目录下。

    Returns:
        恢复目录路径、写入文件数与实际写入字节数（按解压后大小计）。

    Raises:
        SnapshotInputError: 归档不是普通文件、父目录不存在，或目标已存在。
        VerificationError: 归档结构非法或内容与清单不符（成员被截断、摘要不
            匹配、路径穿越等）；失败时不会留下部分恢复结果。
        SnapshotOperationError: 目标在发布瞬间被其他进程占据，或当前文件系统
            无法原子发布目录。
    """

    archive_path = _require_archive(archive)
    destination = Path(destination)
    parent = destination.parent

    if not parent.is_dir():
        raise SnapshotInputError(
            f"destination parent is not an existing directory: {parent}"
        )
    # 同样用 lexists：空目录、普通文件与断链都算已存在，一律拒绝合并或覆盖。
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
                    # "xb" 为独占创建：暂存目录虽由本调用新建，也不允许目标已存在，
                    # 从而排除并发预置的同名文件或符号链接被跟随写入。
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
    """确认参数指向已存在的普通文件。

    只判断路径本身，不解析归档内容：``verify_archive`` 与 ``restore_archive``
    靠它把「路径写错」（输入错误、退出码 2）与「归档损坏」（校验错误、退出码
    1）区分成两类错误。

    Args:
        archive: 调用方传入的归档路径。

    Returns:
        规整为 ``Path`` 后的同一路径。

    Raises:
        SnapshotInputError: 路径不存在、是目录、是断链，或指向非普通文件。
    """
    archive_path = Path(archive)
    if not archive_path.is_file():
        raise SnapshotInputError(f"archive is not an existing file: {archive_path}")
    return archive_path


def _rename_windows_no_replace(source: Path, target: Path) -> None:
    """在保持 rename 不覆盖语义的前提下重试短暂的 Windows 共享冲突。

    Windows 上 ``os.rename`` 在目标已存在时失败，这正是需要的行为；但杀毒软件、
    索引服务持有的瞬时句柄会返回 winerror 5/32/33（拒绝访问、共享冲突、锁定
    冲突），稍后重试即可成功。因此按 0.05/0.15/0.30 秒退避，最后再试一次且
    不再等待，重试耗尽则原样抛出。

    Args:
        source: 待发布的临时文件或暂存目录。
        target: 目标路径，必须不存在。

    Raises:
        FileExistsError: 目标已存在，或 rename 因目标存在而失败。
        OSError: 其它错误，或重试耗尽后仍是共享冲突。
    """
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
    """原子地用 SOURCE 创建 TARGET，拒绝替换任何已存在对象。

    Windows 的 ``os.rename`` 本身原子且目标存在时失败，沿用该原语并叠加共享
    冲突重试。POSIX 的 ``os.rename`` 可能覆盖目标，因此改用同目录硬链接：
    ``os.link`` 原子且目标已存在时报 ``EEXIST``。硬链接会给 SOURCE 增加一个
    名字，由调用方在清理块中删除。

    文件系统不支持该原语时直接报错，不回退到「可能覆盖」的 rename。

    Args:
        source: 已写入并通过校验的临时文件。
        target: 最终归档路径。

    Raises:
        SnapshotOperationError: 目标在发布过程中出现（拒绝覆盖），或底层原语
            不被当前文件系统支持。
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
    """把暂存目录发布到目标位置，且不替换任何已存在的路径。

    Windows 的目录 rename 原子且拒绝覆盖已存在的文件或目录，直接复用。POSIX
    的 rename 可以覆盖已存在的空目录，因此先用独占 ``os.mkdir`` 抢占目标，再用
    (st_dev, st_ino) 身份和「目录为空」两项复核占位仍是本次创建的那个，最后才
    把已校验的暂存树原子 rename 上去：并发写入者无法让 ``mkdir`` 成功两次，
    而往占位目录里放内容会让最终 rename 失败。

    若占位已被替换或不再为空，则原样保留、不做任何删除。失败清理只删除身份
    匹配且仍为空的目录。

    Args:
        stage: 已完成写入与哈希复核的暂存目录。
        destination: 目标路径，发布前必须不存在。

    Raises:
        SnapshotOperationError: 目标被他人占据或内容发生变化（拒绝覆盖或删除），
            以及当前文件系统无法原子发布目录。
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
            # 只替换上面刚复核过的空占位目录。
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
    """构造「目标在恢复期间出现或被改动」的错误。

    Args:
        destination: 发生冲突的目标路径。

    Returns:
        带统一措辞的异常实例，由调用方 ``raise``。
    """
    return SnapshotOperationError(
        f"destination appeared or changed during restore; refusing to "
        f"overwrite or remove it: {destination}"
    )


def _directory_publish_error(
    destination: Path, error: OSError
) -> SnapshotOperationError:
    """构造「当前文件系统无法原子发布目录」的错误。

    Args:
        destination: 目标路径。
        error: 原始 ``OSError``，其消息保留在结果中，便于定位跨盘 rename、
            只读挂载或权限不足等具体原因。

    Returns:
        带统一措辞的异常实例，由调用方 ``raise``。
    """
    return SnapshotOperationError(
        f"cannot publish restored directory atomically without overwriting on "
        f"this filesystem: {destination}: {error}"
    )


def _directory_identity(path: Path) -> Tuple[int, int]:
    """返回目录的 (st_dev, st_ino) 身份标识。

    用 ``os.lstat`` 而非 ``os.stat``，避免跟随符号链接后把别人的目录误当成
    自己创建的占位目录。

    Args:
        path: 待检查路径。

    Returns:
        设备号与 inode 号组成的元组。

    Raises:
        SnapshotOperationError: 路径不是目录（已被替换为文件、链接或已消失）。
    """
    info = os.lstat(path)
    if not stat.S_ISDIR(info.st_mode):
        raise _destination_conflict(path)
    return (info.st_dev, info.st_ino)


def _reservation_matches(path: Path, identity: Tuple[int, int]) -> bool:
    """判断路径是否仍是同一个目录对象。

    Args:
        path: 待检查路径。
        identity: 之前记录的 (st_dev, st_ino)。

    Returns:
        仍是同一目录返回 ``True``；路径消失、类型改变或被替换为其他对象时返回
        ``False``。这里刻意吞掉 ``OSError``，因为「无法确认」与「不匹配」在调用
        方看来同样意味着不能删除。
    """
    try:
        info = os.lstat(path)
    except OSError:
        return False
    return stat.S_ISDIR(info.st_mode) and (info.st_dev, info.st_ino) == identity


def _directory_is_empty(path: Path) -> bool:
    """检查目录是否为空。

    只探测第一个条目就返回，不做完整枚举：占位目录本应为空，遇到第一个条目
    即可判定「已被写入」。

    Args:
        path: 待检查目录。

    Returns:
        目录中没有任何条目时返回 ``True``。

    Raises:
        OSError: 目录不可读或已不存在。
    """
    with os.scandir(path) as entries:
        return next(entries, None) is None


def _remove_own_empty_reservation(
    destination: Path, reservation: Optional[Tuple[int, int]]
) -> None:
    """只删除本次恢复自己创建的、且仍为空的占位目录。

    双重保险：身份不匹配（已被他人替换）或目录非空（他人写入了内容）时一律
    不动，因此失败清理不会误删并发写入者的数据。``reservation`` 为 ``None``
    表示尚未成功抢占，直接返回。删除失败被静默忽略，避免清理逻辑掩盖原始错误。

    Args:
        destination: 占位目录路径。
        reservation: 抢占成功时记录的身份，未抢占时为 ``None``。
    """

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
    """判断 ``path`` 是否位于 ``parent`` 之下或与之相同。

    依赖 ``pathlib.PurePath.relative_to`` 的纯字符串语义，不回退到
    ``os.path.commonpath``；因此两个参数都必须已经 ``resolve``，否则相对路径或
    未展开的符号链接会得出错误结论。

    Args:
        path: 待判断路径。
        parent: 参照目录。

    Returns:
        在 ``parent`` 内部或与 ``parent`` 相同时返回 ``True``。
    """
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _scan_vault(vault_root: Path) -> List[str]:
    """递归列出 Vault 中所有普通文件的相对路径。

    扫描规则刻意保守：符号链接（包括指向目录的链接）、设备文件、管道等非常规
    文件一律拒绝，避免快照内容取决于链接指向的外部路径；判断目录时使用
    ``follow_symlinks=False``，防止链接目录被递归展开。结果只保留用 "/" 分隔
    的相对路径，并统一排序，因此清单顺序与文件系统枚举顺序无关。

    扫描完成后统一做可移植性校验和大小写冲突检测，把问题一次性报出来，而不是
    在遍历中途因单个路径失败。

    Args:
        vault_root: 已 ``resolve`` 的 Vault 根目录。

    Returns:
        升序排列的相对路径列表。

    Raises:
        SnapshotInputError: 目录不可读、含符号链接或非常规文件，或存在不可移
            植路径与大小写冲突。
    """
    discovered: List[str] = []

    def walk(directory: Path, relative_dir: str) -> None:
        """递归遍历单个目录，把普通文件追加到 ``discovered``。

        目录名先排序再遍历，使结果与文件系统枚举顺序无关；符号链接和非常规文件
        就地抛错而不是跳过，避免快照静默地缺文件或依赖链接指向。

        Args:
            directory: 当前遍历的绝对目录。
            relative_dir: 相对 Vault 根的前缀，根目录传空串。

        Raises:
            SnapshotInputError: 目录不可读，或含符号链接与非常规文件。
        """
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
    """检查相对路径能否安全地跨平台落盘。

    判定标准是「同一路径在 Windows 与 POSIX 上必须落到同一位置且可创建」：
    拒绝空路径、非 UTF-8 可编码字符、绝对路径、反斜杠、Windows 非法字符
    ``: \\ < > " | ? *``、控制字符、空段、``.`` 与 ``..`` 段、以点或空格结尾的
    段（Windows 会静默截断），以及 CON/PRN/NUL/COM1-9/LPT1-9 等保留设备名
    （同时覆盖 ``CON.md`` 这类带扩展名的写法）。

    Args:
        path: 相对路径，使用 "/" 分隔。

    Returns:
        违反规则时返回中文原因说明，合规时返回 ``None``。
    """
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
    """检测大小写不敏感文件系统上的目录/文件冲突。

    对每个路径逐级登记前缀，键为各级前缀的 casefold 结果：若两个前缀仅大小写
    不同，或同名前缀一个是文件、一个是目录，恢复时就会互相覆盖，记为
    ``CASE_COLLISION``。之所以逐级展开，是为了同时发现 ``Notes/A.md`` 与
    ``notes/a.md`` 这类发生在目录层的冲突。

    Args:
        paths: 待检查的相对路径集合。

    Returns:
        冲突问题列表；无冲突时为空列表。
    """

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
    """构造带固定元数据的 ZIP 条目，保证归档可复现。

    Args:
        name: ZIP 成员名，取值为 ``files/...`` 或 ``MANIFEST.json``。

    Returns:
        时间戳固定为 1980-01-01、压缩方式 ZIP_DEFLATED、``create_system=3``
        （Unix）、权限位 0644 的 ``zipfile.ZipInfo``；这些字段不随平台和
        当前时间变化。
    """
    info = zipfile.ZipInfo(name, date_time=_ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    return info


def _manifest_bytes(entries: Sequence[ManifestEntry]) -> bytes:
    """把条目序列编码成 MANIFEST.json 的字节内容。

    固定键名、``sort_keys=True``、最紧凑分隔符和末尾换行，并保留非 ASCII 字符
    原样（``ensure_ascii=False``）；因此同一批条目总是得到完全相同的字节，配合
    固定 ZIP 元数据实现归档级可复现性，也便于人工阅读中文路径。

    Args:
        entries: 按路径升序排列的条目。

    Returns:
        UTF-8 编码、以 ``\\n`` 结尾的 JSON 字节串。
    """
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
    """把 Vault 文件流式写入临时 ZIP，并返回清单条目与总字节数。

    逐文件读取、边读边算 SHA-256 边写入 ZIP，内存占用与单个文件大小无关。
    ``force_zip64=True`` 让成员头一开始就按 ZIP64 布局写出，避免大文件中途触发
    重新打包；``allowZip64=True`` 允许归档整体超过 4 GiB。清单最后写入，因此
    读取方可以先拿到全部负载成员再看到索引。

    Args:
        temp_path: 临时 ZIP 路径，必须位于最终工作目录内，便于随后原子发布。
        vault_root: 已 ``resolve`` 的 Vault 根目录。
        relative_paths: 已排序的相对路径列表。

    Returns:
        ``(entries, total_bytes)``：清单条目列表与未压缩字节总数。

    Raises:
        SnapshotOperationError: 某个文件在扫描后变得不可读（被删除、权限变更、
            被其他进程独占等）。
    """
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
    """解析归档结构，并交叉校验清单与成员。

    只做结构与元数据层面的检查，不重算负载哈希：那一步由
    ``verify_archive`` 与 ``restore_archive`` 按需进行，恢复时还可以在
    写文件的过程中顺带完成。这里把 ``zipfile`` 的多种底层异常统一收敛为
    ``VerificationError``，避免调用方看到 traceback。

    Args:
        archive_path: 已确认为普通文件的归档路径。

    Returns:
        含解析后清单与成员句柄映射的中间结果。

    Raises:
        VerificationError: ZIP 不可读、清单缺失或字段非法、成员与清单不一致。
        SnapshotInputError: 打开归档时发生 I/O 错误。
    """
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
    """按成员名分类 ZIP 条目，并记录全部结构性问题。

    逐条判断：重名成员（解压结果取决于实现细节，必须拒绝）、目录条目、符号
    链接、非常规文件类型、加密标志位、不带 ``files/`` 前缀的未知成员，以及经
    ``_path_error`` 判定不安全的负载路径。清单成员单独返回，负载成员按相对
    路径登记到映射中。

    Args:
        infos: ``zipfile.ZipFile.infolist`` 返回的成员元数据。

    Returns:
        ``(issues, payload_infos, manifest_info)`` 三元组；``manifest_info`` 为
        ``None`` 表示归档里缺少 MANIFEST.json。

    Note:
        这里不抛异常：调用方需要一次拿到全部问题，再决定错误消息与退出码。
    """
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
    """把 MANIFEST.json 字节解析成受信任的清单对象。

    校验非常严格：必须是 UTF-8 JSON 对象，顶层字段集合精确等于
    ``{files, format, version}``，``format`` 必须匹配常量，``version`` 必须是
    int（用 ``type(...) is int`` 排除 ``True`` 这类布尔子类）；每个条目的字段
    集合精确，路径可移植且不重复，``size`` 为非负 int，``sha256`` 为 64 位小写
    十六进制。最后还要求条目按路径升序、无大小写冲突。任何偏差都直接拒绝，不做
    「宽容修复」，否则会把损坏归档读成看似正常的快照。

    Args:
        raw: 从归档中读出的清单字节。

    Returns:
        条目顺序已确认的不可变清单。

    Raises:
        VerificationError: 任一校验失败，``kind`` 为 ``INVALID_MANIFEST`` 或
            ``CASE_COLLISION``。
    """
    def invalid(detail: str) -> VerificationError:
        """按统一的 kind 构造清单错误，避免各处散落字符串常量。

        Args:
            detail: 面向人的具体原因。

        Returns:
            ``kind`` 固定为 ``INVALID_MANIFEST`` 的校验异常，由调用方 ``raise``。
        """
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
    """比对清单与实际成员，找出缺失、多余与声明大小不符。

    检查三类问题：清单列出但归档缺失（``MISSING``）、归档存在但清单未列
    （``UNEXPECTED``）、以及同名成员声明大小与实际大小不符（``TAMPERED``）。
    三者都基于 ``ZipInfo.file_size``，只说明元数据不一致；内容是否被替换仍由
    ``_check_payload_hashes`` 复核。

    Args:
        manifest: 解析后的清单。
        payload_infos: 相对路径到成员元数据的映射。

    Returns:
        去重并排序后的问题列表；完全一致时为空列表。
    """
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
    """流式重算每个负载成员的 SHA-256 并与清单比对。

    按 ``_CHUNK_SIZE`` 分块读取，避免把大文件整体载入内存。单个成员解压
    失败（CRC 错误、数据被截断、压缩方法不支持等）只记录一条 ``TAMPERED`` 并
    继续检查其余成员，因此一次能报出全部受损文件。归档在读取过程中被替换或
    损坏时抛异常，而不是返回空问题列表。

    Args:
        archive_path: 归档路径；会重新打开一次以取得独立的读取句柄。
        inspection: 已通过结构校验的解析结果，用于复用成员元数据。

    Returns:
        去重并排序后的问题列表；全部匹配时为空列表。

    Raises:
        VerificationError: 读取过程中归档结构损坏或被整体替换。
        SnapshotInputError: 打开归档时发生 I/O 错误。
    """
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
    """对问题去重并按 (kind, detail) 升序排列。

    Args:
        issues: 原始问题序列，允许重复（同一路径可能同时被多条规则命中）。

    Returns:
        不可变元组；``Issue`` 是 ``order=True`` 的冻结数据类，可直接参与排序，
        因此错误输出与测试断言都是稳定的。
    """
    return tuple(sorted(set(issues)))
