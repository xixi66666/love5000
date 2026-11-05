"""生成离线交互式数据操作台 output/console.html。

设计目标：单个 HTML 文件，双击即可用，不依赖网络与后端。
数据在构建时嵌入，页面里可以任意排序、筛选、重排列、看走势、做透视。
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .data import DATA_DIR, OUTPUT_DIR, load
from .features import draw_features

TEMPLATE_PATH = Path(__file__).with_name("console_template.html")
OUTPUT_PATH = OUTPUT_DIR / "console.html"

COLUMNS = [
    "issue", "date", "front", "back", "sum", "span", "odd", "big", "zone",
    "consec", "maxrun", "ac", "repeat", "sales", "pool",
    "p1c", "p1a", "p2c", "p2a", "pc", "pa",
]

# 奖级条件（已用中奖注数比例与理论概率核对过的规则）
SSQ_LEVELS = [
    {"name": "一等奖", "cond": "6 红 + 1 蓝"},
    {"name": "二等奖", "cond": "6 红 + 0 蓝"},
    {"name": "三等奖", "cond": "5 红 + 1 蓝"},
    {"name": "四等奖", "cond": "5+0 或 4+1"},
    {"name": "五等奖", "cond": "4+0 或 3+1"},
    {"name": "六等奖", "cond": "0–2 红 + 1 蓝"},
]

DLT_LEVELS = {
    7: [
        {"name": "一等奖", "cond": "5 前 + 2 后"},
        {"name": "二等奖", "cond": "5 前 + 1 后"},
        {"name": "三等奖", "cond": "5+0 或 4+2"},
        {"name": "四等奖", "cond": "4+1"},
        {"name": "五等奖", "cond": "4+0 或 3+2"},
        {"name": "六等奖", "cond": "3+1 或 2+2"},
        {"name": "七等奖", "cond": "3+0 / 2+1 / 1+2 / 0+2"},
    ],
    9: [
        {"name": "一等奖", "cond": "5 前 + 2 后"},
        {"name": "二等奖", "cond": "5 前 + 1 后"},
        {"name": "三等奖", "cond": "5+0"},
        {"name": "四等奖", "cond": "4+2"},
        {"name": "五等奖", "cond": "4+1"},
        {"name": "六等奖", "cond": "3+2"},
        {"name": "七等奖", "cond": "4+0"},
        {"name": "八等奖", "cond": "3+1 或 2+2"},
        {"name": "九等奖", "cond": "3+0 / 2+1 / 1+2 / 0+2"},
    ],
    6: [
        {"name": "一等奖", "cond": "5 前 + 2 后"},
        {"name": "二等奖", "cond": "5 前 + 1 后"},
        {"name": "三等奖", "cond": None},
        {"name": "四等奖", "cond": None},
        {"name": "五等奖", "cond": None},
        {"name": "六等奖", "cond": None},
    ],
}

LEVEL_NAMES = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def _int(value):
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(number):
        return None
    return int(number)


def _prize_arrays_ssq(df: pd.DataFrame) -> tuple[list, list]:
    counts, amounts = [], []
    for i in range(len(df)):
        row_c, row_a = [], []
        for tier in range(1, 7):
            row_c.append(_int(df[f"p{tier}_count"].iloc[i]))
            row_a.append(_int(df[f"p{tier}_amount"].iloc[i]))
        counts.append(row_c)
        amounts.append(row_a)
    return counts, amounts


def _prize_arrays_dlt(issues: pd.Series) -> tuple[dict, dict]:
    raw = pd.read_csv(DATA_DIR / "dlt_prizes.csv", encoding="utf-8-sig")
    raw = raw[(raw["is_add"] == 0) & raw["level_name"].isin([f"{k}等奖" for k in LEVEL_NAMES])]
    raw = raw.assign(tier=raw["level_name"].str[0].map(LEVEL_NAMES))
    raw = raw.dropna(subset=["tier"])
    counts, amounts = {}, {}
    for issue, group in raw.groupby("issue"):
        group = group.sort_values("tier")
        counts[int(issue)] = [_int(v) for v in group["count"]]
        amounts[int(issue)] = [_int(v) for v in group["amount"]]
    fallback_c, fallback_a = [], []
    return counts, amounts


def build_game(key: str) -> dict:
    data = load(key)
    game = data.game
    df = data.df
    feats = draw_features(data)

    if key == "ssq":
        prize_c, prize_a = _prize_arrays_ssq(df)
        extra = []
    else:
        dlt_c, dlt_a = _prize_arrays_dlt(df["issue"])
        prize_c, prize_a = [], []
        for issue in df["issue"].tolist():
            issue = int(issue)
            if issue in dlt_c:
                prize_c.append(dlt_c[issue])
                prize_a.append(dlt_a[issue])
            else:
                prize_c.append([_int(df.loc[df.issue == issue, f"p{t}_count"].iloc[0]) for t in (1, 2)])
                prize_a.append([_int(df.loc[df.issue == issue, f"p{t}_amount"].iloc[0]) for t in (1, 2)])
        extra = ["p1ac", "p1aa", "p2ac", "p2aa"]

    rows = []
    for i in range(len(df)):
        record = df.iloc[i]
        feature = feats.iloc[i]
        pc = prize_c[i]
        pa = prize_a[i]
        row = [
            int(record["issue"]),
            int(pd.Timestamp(record["date"]).strftime("%Y%m%d")),
            [int(v) for v in np.flatnonzero(data.front[i]) + 1],
            [int(v) for v in np.flatnonzero(data.back[i]) + 1],
            int(feature["sum"]),
            int(feature["span"]),
            int(feature["odd"]),
            int(feature["big"]),
            str(feature["zone_pattern"]),
            int(feature["consecutive"]),
            int(feature["max_run"]),
            int(feature["ac"]),
            None if pd.isna(feature["repeat"]) else int(feature["repeat"]),
            _int(record["sales"]),
            _int(record["pool"]),
            pc[0] if len(pc) > 0 else None,
            pa[0] if len(pa) > 0 else None,
            pc[1] if len(pc) > 1 else None,
            pa[1] if len(pa) > 1 else None,
            pc,
            pa,
        ]
        if extra:
            row.extend([_int(record["p1_add_count"]), _int(record["p1_add_amount"]),
                        _int(record["p2_add_count"]), _int(record["p2_add_amount"])])
        rows.append(row)

    cols = COLUMNS + extra
    if key == "ssq":
        levels = {6: SSQ_LEVELS}
        tiers = 6
    else:
        levels = DLT_LEVELS
        tiers = max(len(c) for c in prize_c)

    return {
        "name": game.name,
        "frontPool": game.front_pool,
        "frontPick": game.front_pick,
        "backPool": game.back_pool,
        "backPick": game.back_pick,
        "cols": cols,
        "levels": {str(k): v for k, v in levels.items()},
        "tiers": tiers,
        "rows": rows,
    }


def build() -> dict:
    payload = {key: build_game(key) for key in ("ssq", "dlt")}
    return payload


DEFAULT_NOTE = "双击项目根目录的「启动操作台.bat」，或在命令行运行 python scripts/serve.py --open。"


def write_console(port: int = 8777, note: str | None = None, tip: str | None = None) -> Path:
    """生成操作台 HTML；port/note 用于「刷新数据」按钮连本地服务。"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = build()
    data_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    data_json = data_json.replace("</", "<\\/")

    config = {
        "port": int(port),
        "note": note if note is not None else DEFAULT_NOTE,
        "tip": tip or f"请通过 http://127.0.0.1:{int(port)}/ 打开",
    }

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    if "__DATA__" not in template or "__CONFIG__" not in template:
        raise RuntimeError("模板缺少 __DATA__ / __CONFIG__ 占位符")
    html = (
        template.replace("__CONFIG__", json.dumps(config, ensure_ascii=False))
        .replace("__DATA__", data_json)
    )
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    size = OUTPUT_PATH.stat().st_size / 1024
    print(f"  [OK] {OUTPUT_PATH}（{size:,.0f} KB · 双色球 {len(payload['ssq']['rows']):,} 期 / 大乐透 {len(payload['dlt']['rows']):,} 期）")
    return OUTPUT_PATH


if __name__ == "__main__":
    write_console()
