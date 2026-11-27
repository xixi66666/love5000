#!/usr/bin/env python
"""增量更新开奖数据，并在有新数据时重建报告与操作台。

与 scripts/fetch_ssq.py / fetch_dlt.py 的全量抓取不同，本脚本只拉最新几页，
判断有没有比本地更新的期次，有才追加、备份、重建。

用法：
    python scripts/update_daily.py              # 增量更新 + 有新数据就重建
    python scripts/update_daily.py --check      # 只看有没有新数据，不写文件
    python scripts/update_daily.py --no-build   # 只更新数据，不重建报告
    python scripts/update_daily.py --loop 240   # 常驻，每 240 分钟跑一次

命令行参数与默认值：
    --data-dir      数据目录，默认 <lottery>/data（测试传临时目录）。
    --check         只抓取并汇总有没有新数据，不写任何文件。
    --no-build      只更新数据，不触发重建。
    --force-build   即使没有新数据也重建一次。
    --loop          常驻模式的间隔分钟数，默认 0 表示只跑一次；实际间隔不小于 60 分钟。
    --log           日志文件，默认 <lottery>/logs/update.log。
    --build-target  full（报告+图表+操作台，默认）或 console（只重建操作台）。
    --console-port  console 重建时写进刷新按钮的端口，默认 8777；服务端调用时传 5179。

数据安全约定（修改本文件时必须保持）：
  * 先校验后追加：`validate_ssq` / `validate_dlt` 在写盘前拒绝旧期号、越界号码与重号。
  * 每次真正写盘前备份到 `data/backup/<时间戳>/`，只保留最近 10 份。
  * 失败不动现有数据：抓取、合并或序列化失败都在写目标文件之前返回 1；
    发布阶段中途失败会用本轮备份逐个补偿已发布文件。
  * 同一数据目录同时只允许一个更新进程（`_data_lock`），拿不到锁直接返回 1。
  * 日志同时写 stdout 与日志文件；`server.py` 把子进程输出按纯文本流回页面。

退出码：0 表示本轮成功（含「无更新」与 `--check`）；1 表示抓取失败、校验失败、
发布失败、缺少基础数据文件或已有另一个更新进程；`--loop` 模式下单轮失败只记录并
继续，收到 Ctrl+C 时返回 0。
"""

from __future__ import annotations

import argparse
import errno
import numbers
import os
import shutil
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import pandas as pd

if os.name == "nt":  # pragma: no cover - 平台分支
    import msvcrt
else:  # pragma: no cover - 平台分支
    import fcntl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from _common import get_json, to_int  # noqa: E402

SSQ_API = "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice"
SSQ_HEADERS = {"Referer": "https://www.cwl.gov.cn/ygkj/wqkjgg/ssq/"}
DLT_API = "https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry"
DLT_HEADERS = {"Referer": "https://static.sporttery.cn/"}

LEVEL_NAMES_SSQ = {1: "一等奖", 2: "二等奖", 3: "三等奖", 4: "四等奖", 5: "五等奖", 6: "六等奖"}


def log(path: Path, message: str) -> None:
    """追加一条带时间戳的日志，同时写 stdout 与日志文件。

    Args:
        path: 日志文件路径，父目录不存在时自动创建。
        message: 日志正文，时间戳由本函数补上。

    stdout 立即 flush、文件逐行追加，是为了让 `server.py` 以管道逐行读取时能看到
    实时进度，而不是等缓冲区填满才一次性吐出。`pythonw` 下 `sys.stdout` 为 `None`，
    因此打印前先判空。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {message}"
    if sys.stdout is not None:  # pythonw 下没有控制台
        print(line, flush=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _safe_log(path: Path, message: str) -> None:
    """日志写不进去时不能影响数据发布或补偿。

    发布与补偿路径本身已在处理异常，这里若再抛出 IO 异常会掩盖真正的失败原因，
    因此统一吞掉。
    """
    try:
        log(path, message)
    except Exception:
        pass


LOCK_NAME = ".update.lock"


class UpdateLocked(RuntimeError):
    """同一数据目录已有另一个更新进程。"""


@contextmanager
def _data_lock(data_dir: Path):
    """同一数据目录的跨进程更新锁，进程退出时由操作系统释放。

    使用 data_dir 下的隐藏锁文件：Windows 走 msvcrt，POSIX 走 flock。
    非阻塞获取，拿不到说明另一进程正在更新，由调用方跳过本轮。
    锁文件不删除，避免删除后新进程锁到不同 inode 而形成双锁。
    """
    path = data_dir / LOCK_NAME
    with path.open("ab") as handle:
        handle.seek(0)
        try:
            if os.name == "nt":  # pragma: no cover - 平台分支
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:  # pragma: no cover - 平台分支
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                raise
            raise UpdateLocked(f"数据目录正在被另一个更新进程使用：{path}") from exc
        yield


def _read(path: Path) -> pd.DataFrame:
    """读取开奖或奖级 CSV。

    统一用 `utf-8-sig`：写盘时带 BOM，缺了它 pandas 会把首列名读成带 BOM 前缀的
    「issue」，后续按列名取值就全部落空。文件或列缺失由 pandas 直接抛异常，
    由调用方判定为「缺数据、不写盘」。
    """
    return pd.read_csv(path, encoding="utf-8-sig")


def _coerce_integer_columns(frame: pd.DataFrame) -> None:
    """整数值的数值列转成可空整数，避免 123.0 这种无意义变更。"""
    for column in frame.columns:
        series = frame[column]
        if series.dtype.kind == "f":
            values = series.dropna()
            if values.empty or not (values % 1 == 0).all():
                continue
            frame[column] = series.astype("Int64")
        elif series.dtype == object:
            # 新旧行拼接时，含空值的数值列可能退化成 object（例如 4.0/None 混排）。
            values = series.dropna()
            if values.empty or not all(
                isinstance(value, numbers.Real) and not isinstance(value, bool)
                for value in values
            ):
                continue
            numeric = pd.to_numeric(series, errors="coerce")
            numeric_values = numeric.dropna()
            if numeric_values.empty or not (numeric_values % 1 == 0).all():
                continue
            frame[column] = numeric.astype("Int64")


def _temp_path(path: Path) -> Path:
    """同目录临时文件，确保 os.replace 不会跨文件系统。"""
    return path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")


def _discard_temp(path: Path) -> None:
    """尽力删除临时文件；清理失败不上抛，避免掩盖真正的发布异常。"""
    try:
        path.unlink()
    except OSError:
        pass


def _stage(path: Path, frame: pd.DataFrame) -> Path:
    """把数据序列化到同目录独占临时文件，返回待发布路径。

    只写临时文件，不碰目标文件；调用方可以在全部文件都写成功后再统一替换。
    """
    _coerce_integer_columns(frame)
    temp = _temp_path(path)
    try:
        with temp.open("x", newline="", encoding="utf-8-sig") as handle:
            frame.to_csv(handle, index=False, na_rep="")
            handle.flush()
            os.fsync(handle.fileno())
        return temp
    except BaseException:
        _discard_temp(temp)
        raise


# ---------------------------------------------------------------------------
# 抓取
# ---------------------------------------------------------------------------
def fetch_ssq(since: int, max_pages: int = 3) -> tuple[list[dict], list[dict]]:
    """抓取双色球中比 `since` 更新的期次，从最新一页往回读。

    Args:
        since: 本地已有最大期号；遇到不更新的期次即停止翻页。
        max_pages: 最多翻页数，默认 3 页（每页 100 期），足够覆盖停机数天。

    Returns:
        `(rows, prizes)`：开奖行与六档奖级明细，均只含 `issue > since` 的期次；
        没有新期次时返回两个空列表。

    Raises:
        RuntimeError: 网络或 HTTP 失败（由 `_common.get_json` 抛出）。
        KeyError / ValueError: 上游字段缺失或号码无法解析，调用方据此整轮放弃，
            不写任何数据。
    """
    rows, prizes = [], []
    for page in range(1, max_pages + 1):
        payload = get_json(
            SSQ_API,
            params={"name": "ssq", "pageNo": page, "pageSize": 100, "systemType": "PC"},
            headers=SSQ_HEADERS,
        )
        items = payload.get("result") or []
        if not items:
            break
        stop = False
        for item in items:
            issue = int(str(item["code"]).strip())
            if issue <= since:
                stop = True
                continue
            reds = [int(v) for v in str(item["red"]).split(",")]
            blue = int(item["blue"])
            date = str(item["date"]).strip()[:10]
            row = {
                "issue": issue,
                "date": date,
                "blue": blue,
                "blue2": to_int(item.get("blue2")),
                "sales": to_int(item.get("sales")),
                "pool": to_int(item.get("poolmoney")),
                "source": "cwl.gov.cn",
                "aux_source": None,
            }
            for index, value in enumerate(reds, start=1):
                row[f"red{index}"] = value

            for grade in item.get("prizegrades") or []:
                level = to_int(grade.get("type"))
                if level not in LEVEL_NAMES_SSQ:
                    continue
                count = to_int(grade.get("typenum"))
                amount = to_int(grade.get("typemoney"))
                row[f"p{level}_count"] = count
                row[f"p{level}_amount"] = 0 if count == 0 else amount
                prizes.append(
                    {
                        "issue": issue,
                        "date": date,
                        "level": level,
                        "level_name": LEVEL_NAMES_SSQ[level],
                        "count": count,
                        "amount": 0 if count == 0 else amount,
                        "source": "cwl.gov.cn",
                    }
                )
            rows.append(row)
        if stop:
            break
    return rows, prizes


def _normalize_level(value) -> str:
    """把奖级名称的括号与空白归一化，用于判断追加奖。

    官方在同一字段里混用全角/半角括号，先归一化才能可靠比较 `一等奖` 这类基名。
    """
    return (
        str(value or "")
        .strip()
        .replace("（", "(")
        .replace("）", ")")
        .replace(" ", "")
    )


def fetch_dlt(since: int, max_pages: int = 3) -> tuple[list[dict], list[dict]]:
    """抓取大乐透中比 `since` 更新的期次，从最新一页往回读。

    大乐透的奖级名称带「(追加)」后缀，同一期有普通与追加两套奖金，因此这里把
    `(基名, 是否追加)` 当作键归并奖级，再拆成一、二等奖的普通/追加四个字段。

    Args:
        since: 本地已有最大期号；遇到不更新的期次即停止翻页。
        max_pages: 最多翻页数，默认 3 页（每页 100 期）。

    Returns:
        `(rows, prizes)`：开奖行与奖级明细，均只含 `issue > since` 的期次；
        没有新期次时返回两个空列表。

    Raises:
        RuntimeError: 网络或 HTTP 失败。
        KeyError / ValueError: 上游字段缺失，或开奖号码不是 7 个合法数字。
            这类数据直接放弃整轮，避免把错号码写进历史。
    """
    rows, prizes = [], []
    for page in range(1, max_pages + 1):
        payload = get_json(
            DLT_API,
            params={"gameNo": 85, "provinceId": 0, "pageSize": 100, "isVerify": 1, "pageNo": page},
            headers=DLT_HEADERS,
        )
        items = (payload.get("value") or {}).get("list") or []
        if not items:
            break
        stop = False
        for item in items:
            issue = int(str(item["lotteryDrawNum"]).strip())
            if issue <= since:
                stop = True
                continue
            numbers = [to_int(v) for v in str(item["lotteryDrawResult"]).split()]
            if len(numbers) != 7 or any(v is None for v in numbers):
                raise ValueError(f"bad draw result {issue}: {item['lotteryDrawResult']!r}")
            front, back = numbers[:5], numbers[5:]
            date = str(item["lotteryDrawTime"]).strip()[:10]

            row = {
                "issue": issue,
                "date": date,
                "sales": to_int(item.get("totalSaleAmount")),
                "pool": to_int(item.get("poolBalanceAfterdraw")) or to_int(item.get("poolBalance")),
                "source": "sporttery.cn",
                "aux_source": None,
                "quality_flag": None,
            }
            for index, value in enumerate(front, start=1):
                row[f"front{index}"] = value
            for index, value in enumerate(back, start=1):
                row[f"back{index}"] = value

            levels = {}
            for grade in item.get("prizeLevelList") or []:
                name = _normalize_level(grade.get("prizeLevel"))
                is_add = name.endswith("(追加)")
                base = name[: -len("(追加)")] if is_add else name
                count = to_int(grade.get("stakeCount"))
                amount = to_int(grade.get("stakeAmount"))
                levels[(base, is_add)] = {"count": count, "amount": 0 if count == 0 else amount}
                prizes.append(
                    {
                        "issue": issue,
                        "date": date,
                        "sort": to_int(grade.get("sort")),
                        "level_name": name,
                        "is_add": int(is_add),
                        "count": count,
                        "amount": 0 if count == 0 else amount,
                        "source": "sporttery.cn",
                        "quality_flag": None,
                    }
                )

            for base, prefix in (("一等奖", "p1"), ("二等奖", "p2")):
                normal = levels.get((base, False), {})
                added = levels.get((base, True), {})
                row[f"{prefix}_count"] = normal.get("count")
                row[f"{prefix}_amount"] = normal.get("amount")
                row[f"{prefix}_add_count"] = added.get("count")
                row[f"{prefix}_add_amount"] = added.get("amount")
            rows.append(row)
        if stop:
            break
    return rows, prizes


# ---------------------------------------------------------------------------
# 校验与写回
# ---------------------------------------------------------------------------
def validate_ssq(rows: list[dict], since: int) -> None:
    """校验双色球新行，任何一条不合法就整轮放弃。

    这是写盘前的最后一道闸门，检查三件事：期号确实比本地新（上游回退或镜像错乱
    会导致重复追加）、6 个红球互不相同且都在 1-33、蓝球在 1-16。

    Args:
        rows: `fetch_ssq` 返回的开奖行，可为空（无更新时视为通过）。
        since: 本地已有最大期号。

    Raises:
        ValueError: 期号没有变新、红球非法或蓝球非法。
    """
    for row in rows:
        issue = row["issue"]
        if issue <= since:
            raise ValueError(f"期次没有变新：{issue} <= {since}")
        reds = [row[f"red{i}"] for i in range(1, 7)]
        if len(set(reds)) != 6 or not all(1 <= v <= 33 for v in reds):
            raise ValueError(f"{issue} 红球非法：{reds}")
        if not 1 <= row["blue"] <= 16:
            raise ValueError(f"{issue} 蓝球非法：{row['blue']}")


def validate_dlt(rows: list[dict], since: int) -> None:
    """校验大乐透新行，任何一条不合法就整轮放弃。

    与双色球的差别只在区域：前区 5 个互不相同且都在 1-35，后区 2 个互不相同且都在
    1-12；期号仍需严格大于本地最大值。

    Args:
        rows: `fetch_dlt` 返回的开奖行，可为空（无更新时视为通过）。
        since: 本地已有最大期号。

    Raises:
        ValueError: 期号没有变新、前区非法或后区非法。
    """
    for row in rows:
        issue = row["issue"]
        if issue <= since:
            raise ValueError(f"期次没有变新：{issue} <= {since}")
        front = [row[f"front{i}"] for i in range(1, 6)]
        back = [row[f"back{i}"] for i in range(1, 3)]
        if len(set(front)) != 5 or not all(1 <= v <= 35 for v in front):
            raise ValueError(f"{issue} 前区非法：{front}")
        if len(set(back)) != 2 or not all(1 <= v <= 12 for v in back):
            raise ValueError(f"{issue} 后区非法：{back}")


def backup(data_dir: Path, stamp: str) -> Path:
    """把当前四个 CSV 复制到 `data/backup/<stamp>/`，并清理过旧备份。

    Args:
        data_dir: 数据目录。
        stamp: 目录名时间戳，由调用方用 `%Y%m%d_%H%M%S_%f` 生成，保证多次运行不重名。

    Returns:
        本轮备份目录；发布中途失败时用它逐个补偿已发布的文件。

    只保留最近 10 份：每轮都留档会让目录无限增长，10 份已够覆盖连续排障。
    只复制存在的文件，首次运行还没有奖级 CSV 时不会因此失败。
    """
    target = data_dir / "backup" / stamp
    target.mkdir(parents=True, exist_ok=True)
    for name in ("ssq.csv", "dlt.csv", "ssq_prizes.csv", "dlt_prizes.csv"):
        source = data_dir / name
        if source.exists():
            shutil.copy2(source, target / name)
    # 只保留最近 10 份
    backups = sorted((data_dir / "backup").iterdir()) if (data_dir / "backup").exists() else []
    for old in backups[:-10]:
        shutil.rmtree(old, ignore_errors=True)
    return target


def prepare_merge(
    main_path: Path,
    prize_path: Path,
    rows: list[dict],
    prizes: list[dict],
) -> tuple[tuple[Path, pd.DataFrame], tuple[Path, pd.DataFrame]]:
    """只读取并准备合并结果，不写盘；返回 (奖级, 开奖) 顺序的待发布项。"""
    main = _read(main_path)
    if rows:
        cols = list(main.columns)
        new = pd.DataFrame(rows).reindex(columns=cols)
        main = pd.concat([main, new], ignore_index=True)
    main = main.drop_duplicates(subset=["issue"], keep="last")
    main = main.sort_values(["date", "issue"], kind="mergesort").reset_index(drop=True)

    prize = _read(prize_path)
    if prizes:
        cols = list(prize.columns)
        new = pd.DataFrame(prizes).reindex(columns=cols)
        prize = pd.concat([prize, new], ignore_index=True)
    subset = ["issue", "level_name", "is_add"] if "is_add" in prize.columns else ["issue", "level"]
    prize = prize.drop_duplicates(subset=subset, keep="last")
    prize = prize.sort_values(["issue", "sort"] if "sort" in prize.columns else ["issue", "level"],
                              kind="mergesort").reset_index(drop=True)
    return (prize_path, prize), (main_path, main)


def _restore_from_backup(path: Path, backup_path: Path) -> None:
    """用本轮备份原子恢复单个文件。"""
    temp = _temp_path(path)
    try:
        shutil.copy2(backup_path, temp)
        os.replace(temp, path)
    except BaseException:
        try:
            temp.unlink()
        except OSError:
            pass
        raise


def publish(
    writes: list[tuple[Path, pd.DataFrame]],
    backup_dir: Path,
    log_path: Path,
) -> None:
    """先序列化本轮全部文件，再按给定顺序逐个原子发布。

    第一步只写同目录独占临时文件；全部成功后才开始 os.replace，因此序列化
    失败时所有目标仍是旧版。第二步中途失败时清掉未发布临时文件，并用本轮
    备份逐个补偿已发布文件；日志不可写也不能打断补偿。

    这是逐文件原子替换，不是跨文件事务。进程被硬中断时只保证每个目标文件
    是完整的新版或旧版，下次运行按开奖文件的最大期次重新抓取，奖级先发布、
    开奖最后发布使同类更新可重试收敛。
    """
    staged: list[tuple[Path, Path]] = []
    current: Path | None = None
    try:
        for path, frame in writes:
            current = path
            staged.append((_stage(path, frame), path))
    except BaseException as exc:
        for temp, _ in staged:
            _discard_temp(temp)
        if current is not None:
            _safe_log(
                log_path,
                f"预写 {current.name} 失败：{type(exc).__name__}: {exc}；目标文件未改动",
            )
        raise

    committed: list[Path] = []
    try:
        for temp, path in staged:
            current = path
            os.replace(temp, path)
            committed.append(path)
            _safe_log(log_path, f"已发布 {path.name}")
    except BaseException as exc:
        for temp, _ in staged[len(committed):]:
            _discard_temp(temp)
        if current is not None:
            _safe_log(log_path, f"发布 {current.name} 失败：{type(exc).__name__}: {exc}")
        for path in reversed(committed):
            source = backup_dir / path.name
            if not source.exists():
                _safe_log(log_path, f"无法恢复 {path.name}：本轮备份不存在")
                continue
            try:
                _restore_from_backup(path, source)
                _safe_log(log_path, f"已用本轮备份恢复 {path.name}")
            except Exception as restore_exc:
                _safe_log(
                    log_path,
                    f"恢复 {path.name} 失败：{type(restore_exc).__name__}: {restore_exc}",
                )
        raise


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def run_once(
    data_dir: Path,
    log_path: Path,
    check_only: bool,
    build: bool,
    force_build: bool = False,
    build_target: str = "full",
    console_port: int = 8777,
) -> int:
    """外层入口：按需取跨进程数据锁后执行一轮更新。

    `--check` 与数据目录不存在时不取锁：前者本来就不写文件，后者没有可锁的目录，
    而且缺目录需要靠 `_run_once` 给出「请先运行全量抓取脚本」的明确提示。

    Args:
        data_dir: 数据目录。
        log_path: 日志文件。
        check_only: 只检查不写盘。
        build: 是否在更新后重建。
        force_build: 无新数据也重建。
        build_target: `full` 或 `console`。
        console_port: console 重建写给刷新按钮的端口。

    Returns:
        进程退出码：0 成功或无需更新，1 失败或同一数据目录已有另一个更新进程。
    """
    args = (data_dir, log_path, check_only, build, force_build, build_target, console_port)
    if check_only or not data_dir.is_dir():
        return _run_once(*args)
    try:
        with _data_lock(data_dir):
            return _run_once(*args)
    except UpdateLocked as exc:
        _safe_log(log_path, str(exc))
        return 1


def _run_once(
    data_dir: Path,
    log_path: Path,
    check_only: bool,
    build: bool,
    force_build: bool,
    build_target: str,
    console_port: int,
) -> int:
    """执行一轮完整流程：读本地最大期号 → 抓取 → 校验 → 备份 → 发布 → 重建。

    顺序刻意固定为「先校验、再备份、最后按奖级→开奖的顺序发布」：奖级文件先发布、
    开奖文件最后发布，中途失败时开奖期次仍是旧值，下一轮会重新抓到同一批数据，
    把两半各自补齐，因此同类失败可以重试收敛。

    Returns:
        进程退出码。所有失败分支都在写目标文件之前或补偿之后返回 1，
        因此返回 1 代表现有数据未被破坏。
    """
    started = time.time()
    ssq_main, ssq_prize = data_dir / "ssq.csv", data_dir / "ssq_prizes.csv"
    dlt_main, dlt_prize = data_dir / "dlt.csv", data_dir / "dlt_prizes.csv"
    for path in (ssq_main, dlt_main):
        if not path.exists():
            log(log_path, f"缺少 {path}，请先运行全量抓取脚本 scripts/fetch_ssq.py / fetch_dlt.py")
            return 1

    since_ssq = int(_read(ssq_main)["issue"].max())
    since_dlt = int(_read(dlt_main)["issue"].max())

    try:
        ssq_rows, ssq_prizes = fetch_ssq(since_ssq)
        dlt_rows, dlt_prizes = fetch_dlt(since_dlt)
    except Exception as exc:  # 网络或解析失败：不动数据
        log(log_path, f"抓取失败：{exc}")
        return 1

    validate_ssq(ssq_rows, since_ssq)
    validate_dlt(dlt_rows, since_dlt)

    def describe(rows, key):
        if not rows:
            return "无更新"
        issues = sorted(r["issue"] for r in rows)
        return f"+{len(rows)} 期（{issues[0]} → {issues[-1]}）"

    summary = f"双色球 {describe(ssq_rows, 'ssq')}｜大乐透 {describe(dlt_rows, 'dlt')}"

    if check_only:
        log(log_path, f"[检查] {summary}（未写入）")
        return 0

    changed = bool(ssq_rows or dlt_rows)
    if changed:
        prize_writes: list[tuple[Path, pd.DataFrame]] = []
        draw_writes: list[tuple[Path, pd.DataFrame]] = []
        try:
            if ssq_rows:
                prize_write, draw_write = prepare_merge(ssq_main, ssq_prize, ssq_rows, ssq_prizes)
                prize_writes.append(prize_write)
                draw_writes.append(draw_write)
            if dlt_rows:
                prize_write, draw_write = prepare_merge(dlt_main, dlt_prize, dlt_rows, dlt_prizes)
                prize_writes.append(prize_write)
                draw_writes.append(draw_write)
        except Exception as exc:
            log(log_path, f"准备写入失败：{type(exc).__name__}: {exc}；本轮未修改数据")
            return 1

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        target = backup(data_dir, stamp)
        log(log_path, f"已备份原始数据 → {target.relative_to(ROOT) if target.is_relative_to(ROOT) else target}")
        try:
            # 奖级先发布、开奖文件最后发布：中途失败时开奖期次仍是旧的，下次会重新抓取。
            publish([*prize_writes, *draw_writes], target, log_path)
        except Exception as exc:
            _safe_log(log_path, f"本轮发布未完成（{type(exc).__name__}: {exc}）；请查看发布/恢复日志")
            return 1

    elapsed = time.time() - started
    if not changed and not force_build:
        log(log_path, f"{summary}｜无需重建（{elapsed:.1f}s）")
        return 0

    if not changed:
        log(log_path, f"{summary}｜按要求强制重建")

    if not build:
        log(log_path, f"{summary}｜数据已更新，跳过重建（{elapsed:.1f}s）")
        return 0

    log(log_path, f"{summary}｜开始重建报告与操作台…")
    # 子进程强制 UTF-8：计划任务里默认是 GBK，遇到 ✓ 之类字符会崩
    child_env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    rebuild_args = [sys.executable, "-X", "utf8", str(ROOT / "main.py")]
    if build_target == "console":
        rebuild_args += ["--console-only", "--port", str(console_port)]
    result = subprocess.run(
        rebuild_args,
        cwd=str(ROOT),
        env=child_env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        log(log_path, f"重建失败：\n{result.stderr[-1500:]}")
        return 1
    tail = [line for line in result.stdout.strip().splitlines() if line.strip()][-2:]
    log(log_path, f"重建完成：{' / '.join(tail)}｜总耗时 {time.time() - started:.1f}s")
    return 0


def main() -> int:
    """解析参数并单次执行，或按分钟数常驻循环。

    `--loop` 的最小间隔被抬到 60 分钟：官方一天只开几期，更密的轮询没有收益，
    也更容易被上游限流。循环里单轮失败只记录并继续，交给下一轮自然重试。

    Returns:
        单次模式的退出码即 `run_once` 的返回值；循环模式在收到 Ctrl+C 时返回 0。
    """
    parser = argparse.ArgumentParser(description="增量更新开奖数据")
    parser.add_argument("--data-dir", default=str(ROOT / "data"), help="数据目录（测试用）")
    parser.add_argument("--check", action="store_true", help="只检查，不写文件")
    parser.add_argument("--no-build", action="store_true", help="不重建报告")
    parser.add_argument("--force-build", action="store_true", help="即使没有新数据也重建一次")
    parser.add_argument("--loop", type=int, default=0, metavar="MINUTES", help="常驻循环，间隔分钟数")
    parser.add_argument("--log", default=str(ROOT / "logs" / "update.log"), help="日志文件")
    parser.add_argument("--build-target", choices=["full", "console"], default="full",
                        help="full=报告+图表+操作台；console=只重建操作台（部署在 love5000 时用）")
    parser.add_argument("--console-port", type=int, default=8777, help="console 重建时写入的刷新端口")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    log_path = Path(args.log)
    build = not args.no_build

    if args.loop <= 0:
        return run_once(data_dir, log_path, args.check, build, args.force_build,
                        args.build_target, args.console_port)

    log(log_path, f"进入循环模式，每 {args.loop} 分钟检查一次（Ctrl+C 退出）")
    try:
        while True:
            code = run_once(data_dir, log_path, args.check, build, args.force_build,
                            args.build_target, args.console_port)
            if code != 0:
                log(log_path, "本轮失败，下一轮继续重试")
            time.sleep(max(60, args.loop) * 60)
    except KeyboardInterrupt:
        log(log_path, "收到中断，退出循环")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
