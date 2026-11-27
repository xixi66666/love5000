"""全量回填大乐透开奖，写出 data/dlt.csv 与 data/dlt_prizes.csv。

Source:
  https://webapi.sporttery.cn official history API（分页抓取）
  500.com 历史页只用于字段补全与交叉核对，不单独贡献期次。

Usage:
  python scripts/fetch_dlt.py

命令行参数：无。

副作用：覆盖写 data/dlt.csv 与 data/dlt_prizes.csv，原始响应保存在 data/raw/dlt/。
官方接口有少量已确认的脏数据，脚本用 FIELD_CORRECTIONS / PRIZE_CORRECTIONS 修正
数值，并把原因写进 quality_flag 列，下游报告据此标注「该期经过人工核对」。

退出码：没有显式退出码。抓取、解析或校验失败时抛异常，进程以 1 退出；此时尚未
写任何 CSV，已有数据保持原样。
"""

from __future__ import annotations

import re
import time
from collections import Counter
from datetime import datetime

from bs4 import BeautifulSoup

from _common import (
    DATA_DIR,
    RAW_DIR,
    get,
    get_json,
    save_json,
    to_int,
    write_csv,
)

API_URL = "https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry"
HEADERS = {"Referer": "https://static.sporttery.cn/"}
BASE_PARAMS = {
    "gameNo": 85,
    "provinceId": 0,
    "pageSize": 100,
    "isVerify": 1,
}
C500_URL = "https://datachart.500.com/dlt/history/newinc/history.php"
C500_HEADERS = {"Referer": "https://datachart.500.com/dlt/"}

FIELDS = [
    "issue",
    "date",
    "front1",
    "front2",
    "front3",
    "front4",
    "front5",
    "back1",
    "back2",
    "sales",
    "pool",
    "p1_count",
    "p1_amount",
    "p1_add_count",
    "p1_add_amount",
    "p2_count",
    "p2_amount",
    "p2_add_count",
    "p2_add_amount",
    "source",
    "aux_source",
    "quality_flag",
]

PRIZE_FIELDS = [
    "issue",
    "date",
    "sort",
    "level_name",
    "is_add",
    "count",
    "amount",
    "source",
    "quality_flag",
]

FIELD_CORRECTIONS = {
    "17052": {"p2_amount": 81082},
    "17062": {
        "p1_count": 2,
        "p2_count": 57,
        "p2_amount": 191426,
        "p2_add_amount": 114855,
    },
    "17063": {
        "p1_count": 11,
        "p1_amount": 6287758,
        "p2_count": 281,
        "p2_amount": 24867,
        "p2_add_count": 106,
        "p2_add_amount": 14920,
    },
}

QUALITY_FLAGS = {
    "17052": (
        "official API p2 amount was 1551723 (actually a bonus value); "
        "corrected to 81082 from the official announcement"
    ),
    "17062": (
        "official API p1/p2 fields corrupted; corrected from the "
        "official announcement"
    ),
    "17063": (
        "official API prize table duplicated 17062; p1/p2 corrected from "
        "the official announcement; low-tier rows are unreliable"
    ),
    "11107": (
        "official post-draw pool 989564 differs from 500.com 20989564; "
        "kept official value"
    ),
    "26098": (
        "official sales 315878206 differs from 500.com 211224461; "
        "kept official value"
    ),
}

PRIZE_QUALITY_ISSUES = {"17052", "17062", "17063"}

PRIZE_CORRECTIONS = {
    ("17052", "二等奖", 0): {"count": 93, "amount": 81082},
    ("17062", "一等奖", 0): {"count": 2, "amount": 10000000},
    ("17062", "二等奖", 0): {"count": 57, "amount": 191426},
    ("17062", "二等奖(追加)", 1): {"count": 19, "amount": 114855},
    ("17063", "一等奖", 0): {"count": 11, "amount": 6287758},
    ("17063", "二等奖", 0): {"count": 281, "amount": 24867},
    ("17063", "二等奖(追加)", 1): {"count": 106, "amount": 14920},
}


def parse_date(value):
    """把上游日期时间归一化成 ISO 日期字符串。

    官方 `lotteryDrawTime` 带时分秒，统一截前 10 位再解析；解析失败抛
    `ValueError`，宁可整轮中止也不写入畸形日期。
    """
    return datetime.strptime(str(value).strip()[:10], "%Y-%m-%d").date().isoformat()


def normalize_level_name(value):
    """统一官方奖级名称的写法。

    官方在同一字段里混用全角/半角括号并可能夹空格，先归一化才能可靠判断
    `(追加)` 后缀，否则追加奖会被错认成普通奖级，奖金列会串位。

    Args:
        value: 原始奖级名称，可为 `None`。

    Returns:
        去掉空白、括号统一为半角后的名称；空值返回空字符串。
    """
    return (
        str(value or "")
        .strip()
        .replace("（", "(")
        .replace("）", ")")
        .replace(" ", "")
    )


def parse_number(value, low, high, label):
    """解析并校验一个球号，越界即中止本轮抓取。

    Args:
        value: 单元格或 JSON 字段原文。
        low: 允许的最小号码。
        high: 允许的最大号码（前区 35、后区 12）。
        label: 写进错误信息的字段名，便于判断是哪个区出错。

    Raises:
        ValueError: 无法解析为整数或超出 `[low, high]`。
    """
    number = to_int(value)
    if number is None or not low <= number <= high:
        raise ValueError(f"invalid {label}: {value!r}")
    return number


def fetch_500():
    """抓取并解析 500.com 的大乐透历史开奖表格。

    表格固定 15 列，行用 `\\d{5}` 过滤表头与统计行；结果只用于补全与交叉核对，
    不含奖级明细，因此返回值比官方解析结果薄。

    Returns:
        以期号为键的行字典。

    Raises:
        RuntimeError: 页面中没有 `tablelist` 表格，通常是被反爬拦截或改版。
        ValueError: 期号重复、号码越界或前后区内部重号。
    """
    response = get(
        C500_URL,
        params={"start": "07001", "end": "99999"},
        headers=C500_HEADERS,
        timeout=60,
    )
    html = response.content.decode("utf-8", errors="replace")
    raw_dir = RAW_DIR / "dlt"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "history_500.html").write_text(html, encoding="utf-8")

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="tablelist")
    if table is None:
        raise RuntimeError("500.com DLT table not found")

    rows = {}
    for tr in table.find_all("tr"):
        cells = [cell.get_text(strip=True) for cell in tr.find_all(["td", "th"])]
        if len(cells) != 15 or not re.fullmatch(r"\d{5}", cells[0]):
            continue

        (
            issue,
            f1,
            f2,
            f3,
            f4,
            f5,
            b1,
            b2,
            pool,
            p1_count,
            p1_amount,
            p2_count,
            p2_amount,
            sales,
            date,
        ) = cells

        if issue in rows:
            raise ValueError(f"duplicate issue from 500.com: {issue}")

        front = [
            parse_number(value, 1, 35, "front")
            for value in (f1, f2, f3, f4, f5)
        ]
        back = [parse_number(value, 1, 12, "back") for value in (b1, b2)]
        if len(set(front)) != 5 or len(set(back)) != 2:
            raise ValueError(f"duplicate ball in issue {issue}")

        row = {
            "issue": issue,
            "date": parse_date(date),
            "sales": to_int(sales),
            "pool": to_int(pool),
            "p1_count": to_int(p1_count),
            "p1_amount": to_int(p1_amount),
            "p2_count": to_int(p2_count),
            "p2_amount": to_int(p2_amount),
        }
        for index, value in enumerate(front, start=1):
            row[f"front{index}"] = value
        for index, value in enumerate(back, start=1):
            row[f"back{index}"] = value
        rows[issue] = row

    print(f"500.com: {len(rows):,} draws")
    return rows


def fuse(primary_rows, auxiliary_rows):
    """以官方行为主、用 500.com 补齐缺失字段，并套用人工核对结果。

    补全策略比双色球保守：只有官方为 `None`（销量/奖池另允许为 0）时才取
    500.com 的值，绝不覆盖官方已有数值，因为大乐透官方的销量与奖池口径更权威。
    一、二等奖的金额只在注数大于 0 时补齐，避免为「0 注」补出一个不存在的奖金。

    Args:
        primary_rows: 官方接口解析出的行，以期号为键。
        auxiliary_rows: 500.com 解析出的行，仅作补全来源。

    Returns:
        以期号为键的合并结果。被 500.com 补过字段或命中 `FIELD_CORRECTIONS`
        的期次 `aux_source` 为 `"500.com"`；命中 `QUALITY_FLAGS` 的期次写入
        `quality_flag` 说明。
    """
    merged = {}
    filled_count = 0
    for issue, row in primary_rows.items():
        base = auxiliary_rows.get(issue, {})
        combined = dict(row)
        aux = set()

        for key in ("sales", "pool"):
            if combined.get(key) in (None, 0) and base.get(key) not in (None, 0):
                combined[key] = base[key]
                aux.add("500.com")

        for prefix in ("p1", "p2"):
            count_key = f"{prefix}_count"
            amount_key = f"{prefix}_amount"
            if combined.get(count_key) is None and base.get(count_key) is not None:
                combined[count_key] = base[count_key]
                aux.add("500.com")
            if (
                combined.get(amount_key) is None
                and (combined.get(count_key) or 0) > 0
                and base.get(amount_key) is not None
            ):
                combined[amount_key] = base[amount_key]
                aux.add("500.com")

        combined["aux_source"] = "500.com" if aux else None
        if aux:
            filled_count += 1
        merged[issue] = combined

    for issue, fixes in FIELD_CORRECTIONS.items():
        row = merged.get(issue)
        if row is None:
            continue
        row.update(fixes)
        row["aux_source"] = "500.com"

    for issue, flag in QUALITY_FLAGS.items():
        row = merged.get(issue)
        if row is not None:
            row["quality_flag"] = flag

    for row in merged.values():
        for prefix in ("p1", "p1_add", "p2", "p2_add"):
            if row.get(f"{prefix}_count") == 0:
                row[f"{prefix}_amount"] = 0

    print(f"filled missing sporttery.cn fields from 500.com: {filled_count:,} draws")
    return merged


def fetch_pages():
    """逐页抓取官方历史接口，返回原始分页负载列表。

    第一页决定总页数，其余页间隔 0.25s 串行请求以避开限流；每页 JSON 落盘到
    `data/raw/dlt/`，便于核对某期数据来自哪一次抓取。

    Returns:
        JSON 负载列表，元素形如 `{"value": {"list": [...]}}`。

    Raises:
        RuntimeError: 首页未返回 `pages` / `total`，说明接口不可用或请求参数失效。
    """
    raw_dir = RAW_DIR / "dlt"
    raw_dir.mkdir(parents=True, exist_ok=True)

    first = get_json(
        API_URL,
        params={**BASE_PARAMS, "pageNo": 1},
        headers=HEADERS,
    )
    save_json(raw_dir / "page_001.json", first)

    value = first.get("value") or {}
    page_count = int(value.get("pages") or 0)
    total = int(value.get("total") or 0)
    if not page_count or not total:
        raise RuntimeError("sporttery.cn returned no DLT data")

    pages = [first]
    for page_no in range(2, page_count + 1):
        time.sleep(0.25)
        payload = get_json(
            API_URL,
            params={**BASE_PARAMS, "pageNo": page_no},
            headers=HEADERS,
        )
        save_json(raw_dir / f"page_{page_no:03d}.json", payload)
        pages.append(payload)

    print(f"sporttery.cn: {total:,} draws across {page_count} pages")
    return pages


def parse_pages(pages):
    """把分页负载解析成开奖行与奖级明细行。

    每期空格分隔的 7 个号码拆成前区 5 个 + 后区 2 个，逐项校验去重与范围；
    奖级名称先统一括号写法，再按 `(追加)` 后缀拆出是否追加，最后只保留
    一等奖/二等奖的普通与追加四组数值。奖池优先取开奖后余额，缺失才回退开奖前。

    Args:
        pages: `fetch_pages` 返回的分页负载列表。

    Returns:
        `(rows, prize_rows)`：开奖行以期号为键，奖级明细为按奖级展开的列表。

    Raises:
        ValueError: 期号重复，或号码个数、去重、范围任一不合法。
    """
    rows = {}
    prize_rows = []
    for payload in pages:
        for item in (payload.get("value") or {}).get("list", []):
            issue = str(item["lotteryDrawNum"]).strip()
            if issue in rows:
                raise ValueError(f"duplicate issue: {issue}")
            date = parse_date(item["lotteryDrawTime"])

            numbers = [
                to_int(value)
                for value in str(item["lotteryDrawResult"]).split()
            ]
            if len(numbers) != 7 or any(value is None for value in numbers):
                raise ValueError(
                    f"bad draw result for {issue}: "
                    f"{item['lotteryDrawResult']!r}"
                )
            front = numbers[:5]
            back = numbers[5:]
            if len(set(front)) != 5 or any(not 1 <= n <= 35 for n in front):
                raise ValueError(f"bad front area for {issue}: {front}")
            if len(set(back)) != 2 or any(not 1 <= n <= 12 for n in back):
                raise ValueError(f"bad back area for {issue}: {back}")

            levels = {}
            for grade in item.get("prizeLevelList", []):
                name = normalize_level_name(grade.get("prizeLevel"))
                is_add = name.endswith("(追加)")
                base = name[: -len("(追加)")] if is_add else name
                count = to_int(grade.get("stakeCount"))
                amount = to_int(grade.get("stakeAmount"))
                levels[(base, is_add)] = {"count": count, "amount": amount}
                prize_rows.append(
                    {
                        "issue": issue,
                        "date": date,
                        "sort": to_int(grade.get("sort")),
                        "level_name": name,
                        "is_add": int(is_add),
                        "count": count,
                        "amount": amount,
                        "source": "sporttery.cn",
                    }
                )

            pool = to_int(item.get("poolBalanceAfterdraw"))
            if not pool:
                pool = to_int(item.get("poolBalance"))

            row = {
                "issue": issue,
                "date": date,
                "sales": to_int(item.get("totalSaleAmount")),
                "pool": pool,
                "source": "sporttery.cn",
            }
            for index, value in enumerate(front, start=1):
                row[f"front{index}"] = value
            for index, value in enumerate(back, start=1):
                row[f"back{index}"] = value

            for base, prefix in (("一等奖", "p1"), ("二等奖", "p2")):
                normal = levels.get((base, False), {})
                added = levels.get((base, True), {})
                row[f"{prefix}_count"] = normal.get("count")
                row[f"{prefix}_amount"] = normal.get("amount")
                row[f"{prefix}_add_count"] = added.get("count")
                row[f"{prefix}_add_amount"] = added.get("amount")

            rows[issue] = row
    return rows, prize_rows


def check_rows(rows):
    """打印覆盖范围、来源分布与缺期警告，返回按日期排序的行列表。

    与双色球不同，大乐透期号固定 5 位（`YYNNN`），因此这里把期号格式当作硬校验：
    格式不符说明上游换了编码方式，继续往下算会把年份解析错。

    Args:
        rows: 以期号为键的行字典。

    Returns:
        按 `(date, issue)` 升序排列的行列表，即 CSV 的写出顺序。

    Raises:
        RuntimeError: 传入空字典，此时没有可写的数据。
        ValueError: 期号不是 5 位。
    """
    if not rows:
        raise RuntimeError("no DLT rows")

    by_year = {}
    for issue in rows:
        if len(issue) != 5:
            raise ValueError(f"unexpected issue format: {issue!r}")
        year = 2000 + int(issue[:2])
        by_year.setdefault(year, []).append(int(issue[2:]))

    ordered = sorted(rows.values(), key=lambda item: (item["date"], item["issue"]))
    print(
        f"merged: {len(ordered):,} draws, "
        f"{ordered[0]['date']} .. {ordered[-1]['date']}, "
        f"issues {ordered[0]['issue']} .. {ordered[-1]['issue']}"
    )
    print("sources:", dict(Counter(row["source"] for row in ordered)))

    for year, sequences in sorted(by_year.items()):
        gaps = sorted(set(range(1, max(sequences) + 1)) - set(sequences))
        if gaps:
            preview = ", ".join(str(value) for value in gaps[:10])
            print(f"WARN {year}: {len(gaps)} missing issue(s): {preview}")

    latest = ordered[-1]
    print(
        f"latest: {latest['issue']} {latest['date']} "
        f"{[latest[f'front{i}'] for i in range(1, 6)]} + "
        f"{[latest[f'back{i}'] for i in range(1, 3)]}"
    )
    return ordered


def main():
    """官方分页抓取、500.com 交叉核对、补全后写出两个 CSV。

    交叉核对只统计前 5 条号码差异及注数/数值差异的条数，不改变输出数据——两站
    历史上确有录入与口径差异，最终以官方为准。奖级明细写出前套用
    `PRIZE_CORRECTIONS` 与 `QUALITY_FLAGS`，注数为 0 时金额归零；`sort` 缺失按 0
    排序，保证同一期内奖级顺序稳定。

    Raises:
        RuntimeError / ValueError: 任一环节数据非法时向上抛出，此时尚未写 CSV，
            已有数据保持原样。
    """
    pages = fetch_pages()
    rows, prize_rows = parse_pages(pages)
    five_rows = fetch_500()

    overlap = sorted(set(rows) & set(five_rows))
    number_mismatches = 0
    count_mismatches = 0
    value_mismatches = 0
    for issue in overlap:
        left = rows[issue]
        right = five_rows[issue]
        left_numbers = [left[f"front{i}"] for i in range(1, 6)] + [
            left[f"back{i}"] for i in range(1, 3)
        ]
        right_numbers = [right[f"front{i}"] for i in range(1, 6)] + [
            right[f"back{i}"] for i in range(1, 3)
        ]
        if (
            sorted(left_numbers[:5]) != sorted(right_numbers[:5])
            or sorted(left_numbers[5:]) != sorted(right_numbers[5:])
        ):
            number_mismatches += 1
            if number_mismatches <= 5:
                print(
                    f"WARN number mismatch {issue}: "
                    f"official={left_numbers} 500={right_numbers}"
                )
        if (
            left["p1_count"] != right["p1_count"]
            or left["p2_count"] != right["p2_count"]
        ):
            count_mismatches += 1
        for key in ("sales", "pool", "p1_amount", "p2_amount"):
            official_value = left.get(key)
            fallback_value = right.get(key)
            if (
                official_value not in (None, 0)
                and fallback_value not in (None, 0)
                and official_value != fallback_value
            ):
                value_mismatches += 1
                break

    print(
        f"overlap: {len(overlap):,} issues, "
        f"{number_mismatches} number mismatches, "
        f"{count_mismatches} winner-count mismatches, "
        f"{value_mismatches} sales/pool/prize mismatches"
    )

    merged = fuse(rows, five_rows)
    ordered = check_rows(merged)

    for prize in prize_rows:
        fix = PRIZE_CORRECTIONS.get(
            (prize["issue"], prize["level_name"], prize["is_add"])
        )
        if fix:
            prize.update(fix)
        if prize["count"] == 0:
            prize["amount"] = 0
        if prize["issue"] in PRIZE_QUALITY_ISSUES:
            prize["quality_flag"] = QUALITY_FLAGS[prize["issue"]]

    prize_rows.sort(key=lambda item: (item["issue"], item["sort"] or 0))

    write_csv(DATA_DIR / "dlt.csv", FIELDS, ordered)
    write_csv(DATA_DIR / "dlt_prizes.csv", PRIZE_FIELDS, prize_rows)


if __name__ == "__main__":
    main()
