#!/usr/bin/env python
"""增量更新开奖数据，并在有新数据时重建报告与操作台。

与 scripts/fetch_ssq.py / fetch_dlt.py 的全量抓取不同，本脚本只拉最新几页，
判断有没有比本地更新的期次，有才追加、备份、重建。

用法：
    python scripts/update_daily.py              # 增量更新 + 有新数据就重建
    python scripts/update_daily.py --check      # 只看有没有新数据，不写文件
    python scripts/update_daily.py --no-build   # 只更新数据，不重建报告
    python scripts/update_daily.py --loop 240   # 常驻，每 240 分钟跑一次
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from _common import get_json, to_int  # noqa: E402

SSQ_API = "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice"
SSQ_HEADERS = {"Referer": "https://www.cwl.gov.cn/ygkj/wqkjgg/ssq/"}
DLT_API = "https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry"
DLT_HEADERS = {"Referer": "https://static.sporttery.cn/"}

LEVEL_NAMES_SSQ = {1: "一等奖", 2: "二等奖", 3: "三等奖", 4: "四等奖", 5: "五等奖", 6: "六等奖"}


def log(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {message}"
    if sys.stdout is not None:  # pythonw 下没有控制台
        print(line, flush=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _read(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig")


# ---------------------------------------------------------------------------
# 抓取
# ---------------------------------------------------------------------------
def fetch_ssq(since: int, max_pages: int = 3) -> tuple[list[dict], list[dict]]:
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
    return (
        str(value or "")
        .strip()
        .replace("（", "(")
        .replace("）", ")")
        .replace(" ", "")
    )


def fetch_dlt(since: int, max_pages: int = 3) -> tuple[list[dict], list[dict]]:
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


def merge(main_path: Path, prize_path: Path, rows: list[dict], prizes: list[dict]) -> None:
    main = _read(main_path)
    if rows:
        cols = list(main.columns)
        new = pd.DataFrame(rows).reindex(columns=cols)
        main = pd.concat([main, new], ignore_index=True)
    main = main.drop_duplicates(subset=["issue"], keep="last")
    main = main.sort_values(["date", "issue"], kind="mergesort").reset_index(drop=True)
    main.to_csv(main_path, index=False, encoding="utf-8-sig", na_rep="")

    prize = _read(prize_path)
    if prizes:
        cols = list(prize.columns)
        new = pd.DataFrame(prizes).reindex(columns=cols)
        prize = pd.concat([prize, new], ignore_index=True)
    subset = ["issue", "level_name", "is_add"] if "is_add" in prize.columns else ["issue", "level"]
    prize = prize.drop_duplicates(subset=subset, keep="last")
    prize = prize.sort_values(["issue", "sort"] if "sort" in prize.columns else ["issue", "level"],
                              kind="mergesort").reset_index(drop=True)
    prize.to_csv(prize_path, index=False, encoding="utf-8-sig", na_rep="")


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
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = backup(data_dir, stamp)
        log(log_path, f"已备份原始数据 → {target.relative_to(ROOT) if target.is_relative_to(ROOT) else target}")
        if ssq_rows:
            merge(ssq_main, ssq_prize, ssq_rows, ssq_prizes)
        if dlt_rows:
            merge(dlt_main, dlt_prize, dlt_rows, dlt_prizes)

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
