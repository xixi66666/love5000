"""全量回填双色球开奖，写出 data/ssq.csv 与 data/ssq_prizes.csv。

数据来源（两段拼接；官方接口只覆盖 2013 年之后，更早的期次来自 500.com）：
  2003-2012  https://datachart.500.com/ssq/history/newinc/history.php
  2013-now   https://www.cwl.gov.cn official JSON API

Usage:
  python scripts/fetch_ssq.py

命令行参数：无。

副作用：覆盖写 data/ssq.csv 与 data/ssq_prizes.csv，并把两站的原始响应保存在
data/raw/ssq/ 供回查。合并口径以官方接口为主、官方缺失字段用 500.com 补，
500.com 独有的存量期次保留；号码不一致与缺期只打印 WARN 不中断，因此跑完仍需
看一眼输出里的 WARN 行。

退出码：没有显式退出码。抓取、解析或校验失败时抛异常，进程以 1 退出，且此时
尚未写任何 CSV，已有数据不会被破坏。
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
    normalize_issue_ssq,
    save_json,
    to_int,
    write_csv,
)

CWL_URL = "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice"
CWL_HEADERS = {"Referer": "https://www.cwl.gov.cn/ygkj/wqkjgg/ssq/"}
C500_URL = "https://datachart.500.com/ssq/history/newinc/history.php"
C500_HEADERS = {"Referer": "https://datachart.500.com/ssq/"}
PAGE_SIZE = 100

LEVEL_NAMES = {
    1: "一等奖",
    2: "二等奖",
    3: "三等奖",
    4: "四等奖",
    5: "五等奖",
    6: "六等奖",
}

FIELDS = [
    "issue",
    "date",
    "red1",
    "red2",
    "red3",
    "red4",
    "red5",
    "red6",
    "blue",
    "blue2",
    "sales",
    "pool",
    "p1_count",
    "p1_amount",
    "p2_count",
    "p2_amount",
    "p3_count",
    "p3_amount",
    "p4_count",
    "p4_amount",
    "p5_count",
    "p5_amount",
    "p6_count",
    "p6_amount",
    "source",
    "aux_source",
]

PRIZE_FIELDS = [
    "issue",
    "date",
    "level",
    "level_name",
    "count",
    "amount",
    "source",
]


def parse_date(value):
    """把上游日期归一化成 ISO 字符串。

    500.com 只给日期，官方接口带时分秒，统一截前 10 位再解析；解析失败直接
    抛 `ValueError`，宁可整轮中止也不写入畸形日期。
    """
    return datetime.strptime(str(value).strip()[:10], "%Y-%m-%d").date().isoformat()


def parse_number(value, low, high, label):
    """解析并校验一个球号，越界即中止本轮抓取。

    Args:
        value: 单元格或 JSON 字段原文。
        low: 允许的最小号码。
        high: 允许的最大号码（红球 33、蓝球 16）。
        label: 写进错误信息的字段名，便于判断是哪个来源、哪一类号码出错。

    Raises:
        ValueError: 无法解析为整数或超出 `[low, high]`。
    """
    number = to_int(value)
    if number is None or not low <= number <= high:
        raise ValueError(f"invalid {label}: {value!r}")
    return number


def fetch_500():
    """抓取并解析 500.com 的历史开奖表格。

    页面是单个 HTML 表格，列数固定为 16；先用 `\\d{5,7}` 过滤掉表头与统计行，
    再按位置解包，因此站点一旦调整列顺序会立刻报错，而不是静默错位。
    原始 HTML 落盘到 `data/raw/ssq/history_500.html` 便于复盘。

    Returns:
        `(rows, prize_rows)`：`rows` 以期号为键、值可直接写成 CSV；
        `prize_rows` 只含 1、2 等奖的中奖注数与单注金额。

    Raises:
        RuntimeError: 页面中找不到 `tablelist` 表格，通常是被反爬拦截或改版。
        ValueError: 期号重复、号码越界或红球重复。
    """
    response = get(
        C500_URL,
        params={"start": "03001", "end": "99999"},
        headers=C500_HEADERS,
        timeout=60,
    )
    html = response.content.decode("utf-8", errors="replace")
    raw_dir = RAW_DIR / "ssq"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "history_500.html").write_text(html, encoding="utf-8")

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="tablelist")
    if table is None:
        raise RuntimeError("500.com SSQ table not found")

    rows = {}
    prize_rows = []
    for tr in table.find_all("tr"):
        cells = [cell.get_text(strip=True) for cell in tr.find_all(["td", "th"])]
        if len(cells) != 16 or not re.fullmatch(r"\d{5,7}", cells[0]):
            continue

        (
            raw_issue,
            r1,
            r2,
            r3,
            r4,
            r5,
            r6,
            blue,
            blue2,
            pool,
            p1_count,
            p1_amount,
            p2_count,
            p2_amount,
            sales,
            date,
        ) = cells

        issue = normalize_issue_ssq(raw_issue)
        if issue in rows:
            raise ValueError(f"duplicate issue from 500.com: {issue}")

        reds = [parse_number(value, 1, 33, "red") for value in (r1, r2, r3, r4, r5, r6)]
        if len(set(reds)) != 6:
            raise ValueError(f"duplicate red ball in issue {issue}")

        blue2_value = to_int(blue2)
        if blue2_value is not None and not 1 <= blue2_value <= 16:
            blue2_value = None

        row = {
            "issue": issue,
            "date": parse_date(date),
            "blue": parse_number(blue, 1, 16, "blue"),
            "blue2": blue2_value,
            "sales": to_int(sales),
            "pool": to_int(pool),
            "p1_count": to_int(p1_count),
            "p1_amount": to_int(p1_amount),
            "p2_count": to_int(p2_count),
            "p2_amount": to_int(p2_amount),
            "source": "500.com",
        }
        for index, value in enumerate(reds, start=1):
            row[f"red{index}"] = value
        rows[issue] = row

        for level, count, amount in (
            (1, p1_count, p1_amount),
            (2, p2_count, p2_amount),
        ):
            prize_rows.append(
                {
                    "issue": issue,
                    "date": row["date"],
                    "level": level,
                    "level_name": LEVEL_NAMES[level],
                    "count": to_int(count),
                    "amount": to_int(amount),
                    "source": "500.com",
                }
            )

    print(f"500.com: {len(rows):,} draws")
    return rows, prize_rows


def fetch_cwl():
    """抓取官方接口的全部分页并解析。

    先取第一页读 `pageNum` / `total` 判断总页数，再逐页拉取；页间 sleep 0.25s
    以避开官方站点限流，每页原始 JSON 落盘到 `data/raw/ssq/`。

    Returns:
        `(rows, prize_rows)`：`rows` 以官方 7 位期号为键，含 1-6 等奖的注数与金额；
        `prize_rows` 为按奖级展开的明细，供 `ssq_prizes.csv` 使用。

    Raises:
        RuntimeError: 第一页没有返回期数或页数，说明接口不可用或参数已失效。
        ValueError: 期号重复、红球个数或号码非法。
    """
    raw_dir = RAW_DIR / "ssq"
    raw_dir.mkdir(parents=True, exist_ok=True)
    base_params = {
        "name": "ssq",
        "pageSize": PAGE_SIZE,
        "systemType": "PC",
    }

    first = get_json(
        CWL_URL,
        params={**base_params, "pageNo": 1},
        headers=CWL_HEADERS,
    )
    save_json(raw_dir / "cwl_page_001.json", first)

    page_count = int(first.get("pageNum") or 0)
    total = int(first.get("total") or 0)
    if not page_count or not total:
        raise RuntimeError("cwl.gov.cn returned no SSQ data")

    pages = [first]
    for page_no in range(2, page_count + 1):
        time.sleep(0.25)
        payload = get_json(
            CWL_URL,
            params={**base_params, "pageNo": page_no},
            headers=CWL_HEADERS,
        )
        save_json(raw_dir / f"cwl_page_{page_no:03d}.json", payload)
        pages.append(payload)

    rows = {}
    prize_rows = []
    for payload in pages:
        for item in payload.get("result", []):
            issue = str(item["code"]).strip()
            if issue in rows:
                raise ValueError(f"duplicate issue from cwl.gov.cn: {issue}")

            reds = [
                parse_number(value, 1, 33, "red")
                for value in str(item["red"]).split(",")
            ]
            if len(reds) != 6 or len(set(reds)) != 6:
                raise ValueError(f"bad red balls for issue {issue}: {item['red']!r}")

            blue2_value = to_int(item.get("blue2"))
            if blue2_value is not None and not 1 <= blue2_value <= 16:
                blue2_value = None

            row = {
                "issue": issue,
                "date": parse_date(item["date"]),
                "blue": parse_number(item["blue"], 1, 16, "blue"),
                "blue2": blue2_value,
                "sales": to_int(item.get("sales")),
                "pool": to_int(item.get("poolmoney")),
                "source": "cwl.gov.cn",
            }
            for index, value in enumerate(reds, start=1):
                row[f"red{index}"] = value
            rows[issue] = row

            for grade in item.get("prizegrades", []):
                level = to_int(grade.get("type"))
                if level not in LEVEL_NAMES:
                    continue
                count = to_int(grade.get("typenum"))
                amount = to_int(grade.get("typemoney"))
                row[f"p{level}_count"] = count
                row[f"p{level}_amount"] = amount
                prize_rows.append(
                    {
                        "issue": issue,
                        "date": row["date"],
                        "level": level,
                        "level_name": LEVEL_NAMES[level],
                        "count": count,
                        "amount": amount,
                        "source": "cwl.gov.cn",
                    }
                )

    print(f"cwl.gov.cn: {total:,} draws across {page_count} pages")
    return rows, prize_rows


def check_rows(rows):
    """打印覆盖范围、来源分布与缺期警告，返回按日期排序的行列表。

    只检查与排序，不改写任何字段：缺期可能来自官方停售或数据源差异，因此打印
    WARN 而不抛异常，避免为历史上个别期次阻断整次全量回填。

    Args:
        rows: 以期号为键的行字典。

    Returns:
        按 `(date, issue)` 升序排列的行列表，即 CSV 的写出顺序。

    Raises:
        RuntimeError: 传入空字典，此时没有可写的数据。
    """
    if not rows:
        raise RuntimeError("no SSQ rows")

    by_year = {}
    for issue in rows:
        by_year.setdefault(issue[:4], []).append(int(issue[4:]))

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
        f"{[latest[f'red{i}'] for i in range(1, 7)]} + {latest['blue']}"
    )
    return ordered


def main():
    """两源抓取、交叉核对、合并后写出两个 CSV。

    合并口径：先用 500.com 的存量期次打底，再用官方数据覆盖同期字段；官方为空而
    500.com 有值的字段回填，并把 `aux_source` 记为 `500.com`，便于日后判断某个
    字段究竟来自哪个站点。中奖注数为 0 时金额归零，避免「0 注却有大额奖金」的
    自相矛盾行。

    号码不一致只累计并打印前 5 条 WARN，不改变输出：两站历史上确有录入差异，
    最终以官方号码为准。

    Raises:
        RuntimeError / ValueError: 任一源抓取失败或数据非法时向上抛出，
            此时尚未写 CSV，已有数据保持原样。
    """
    five_rows, five_prizes = fetch_500()
    cwl_rows, cwl_prizes = fetch_cwl()

    overlap = sorted(set(five_rows) & set(cwl_rows))
    mismatches = 0
    for issue in overlap:
        old = five_rows[issue]
        new = cwl_rows[issue]
        old_reds = sorted(old[f"red{i}"] for i in range(1, 7))
        new_reds = sorted(new[f"red{i}"] for i in range(1, 7))
        if old_reds != new_reds or old["blue"] != new["blue"]:
            mismatches += 1
            if mismatches <= 5:
                print(
                    f"WARN number mismatch {issue}: "
                    f"500={old_reds}+{old['blue']} "
                    f"cwl={new_reds}+{new['blue']}"
                )
    print(f"overlap: {len(overlap):,} issues, {mismatches} number mismatches")

    merged = dict(five_rows)
    filled_count = 0
    for issue, row in cwl_rows.items():
        base = five_rows.get(issue, {})
        combined = dict(base)
        aux = set()
        for key, value in row.items():
            if value is None and base.get(key) is not None:
                combined[key] = base[key]
                aux.add("500.com")
            else:
                combined[key] = value
        combined["source"] = "cwl.gov.cn"
        combined["aux_source"] = "500.com" if aux else None
        if aux:
            filled_count += 1
        merged[issue] = combined
    print(f"filled missing cwl.gov.cn fields from 500.com: {filled_count:,} draws")

    for row in merged.values():
        for level in range(1, 7):
            if row.get(f"p{level}_count") == 0:
                row[f"p{level}_amount"] = 0

    ordered = check_rows(merged)

    prize_rows = [
        item for item in five_prizes if item["issue"] not in cwl_rows
    ] + cwl_prizes
    for prize in prize_rows:
        if prize["count"] == 0:
            prize["amount"] = 0
    prize_rows.sort(key=lambda item: (item["issue"], item["level"]))

    write_csv(DATA_DIR / "ssq.csv", FIELDS, ordered)
    write_csv(DATA_DIR / "ssq_prizes.csv", PRIZE_FIELDS, prize_rows)


if __name__ == "__main__":
    main()
