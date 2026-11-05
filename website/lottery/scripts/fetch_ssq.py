"""Fetch every 双色球 draw into data/ssq.csv.

Sources:
  2003-2012  https://datachart.500.com/ssq/history/newinc/history.php
  2013-now   https://www.cwl.gov.cn official JSON API

Usage:
  python scripts/fetch_ssq.py
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
    return datetime.strptime(str(value).strip()[:10], "%Y-%m-%d").date().isoformat()


def parse_number(value, low, high, label):
    number = to_int(value)
    if number is None or not low <= number <= high:
        raise ValueError(f"invalid {label}: {value!r}")
    return number


def fetch_500():
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
