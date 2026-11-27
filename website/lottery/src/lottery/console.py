"""生成离线交互式数据操作台 output/console.html。

设计目标：单个 HTML 文件，双击即可用，不依赖网络与后端。
数据在构建时嵌入，页面里可以任意排序、筛选、重排列、看走势、做透视。

公开面：:func:`build_game`（单个彩种的载荷）、:func:`build`（两种彩种的完整载荷）、
:func:`write_console`（渲染并落盘 HTML）。

输入与输出形状：
    * 输入：``data/<key>.csv``（官方开奖宽表）与 ``data/dlt_prizes.csv``（大乐透奖级长表），
      全部只读，本模块不写 CSV；
    * 输出：``output/console.html``，页面脚本通过 ``__DATA__`` / ``__CONFIG__`` 两个占位符
      注入 JSON，行数据按 :data:`COLUMNS` 的顺序排列。

边界：操作台只是历史数据的查看器，不预测、不推荐号码。“刷新数据”按钮通过
``__CONFIG__`` 里的端口调用本机 ``/api/update``，真正的 CSV 写入由 ``scripts/``
在备份之后完成。
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .data import DATA_DIR, OUTPUT_DIR, load
from .features import draw_features

# 模板与代码同目录发布；产物落在 output/，属于可随时重新生成的文件。
TEMPLATE_PATH = Path(__file__).with_name("console_template.html")
OUTPUT_PATH = OUTPUT_DIR / "console.html"

# 行数据列顺序：必须与 console_template.html 声明的字段顺序完全一致，否则页面表格
# 会整体错列——注入的 JSON 里没有列名，只有位置。
# issue/date 是期号与 YYYYMMDD 日期，front/back 是号码数组，其后是和值与形态特征，
# sales/pool 单位元，p1c..p2a 是一、二等奖注数与单注奖金，pc/pa 是全部奖级的注数与奖金数组。
COLUMNS = [
    "issue", "date", "front", "back", "sum", "span", "odd", "big", "zone",
    "consec", "maxrun", "ac", "repeat", "sales", "pool",
    "p1c", "p1a", "p2c", "p2a", "pc", "pa",
]

# 奖级条件（已用中奖注数比例与理论概率核对过的规则）；只用于页面展示，不参与计算。
SSQ_LEVELS = [
    {"name": "一等奖", "cond": "6 红 + 1 蓝"},
    {"name": "二等奖", "cond": "6 红 + 0 蓝"},
    {"name": "三等奖", "cond": "5 红 + 1 蓝"},
    {"name": "四等奖", "cond": "5+0 或 4+1"},
    {"name": "五等奖", "cond": "4+0 或 3+1"},
    {"name": "六等奖", "cond": "0–2 红 + 1 蓝"},
]

# 大乐透奖级文案：7 = 2026-02 起的合并规则，9 = 旧规则，6 = 数据不足时的占位
# （只有前两级的条件已知，其余留 None，由页面显示为“—”）。
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

# 官方奖级名“一等奖”…“九等奖”的首字 → 数字，用于把长表映射回 1..9 级。
LEVEL_NAMES = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def _int(value):
    """把 CSV 里的数值安全地转成 int，供嵌入 JSON 使用。

    Args:
        value: 任意单元格值，可能是 ``None``、``NaN``、``inf`` 或数字字符串。

    Returns:
        整数；无法解析或非有限值时返回 ``None``，JSON 里序列化为 ``null``，
        页面显示为空而不是 ``NaN`` 或 ``Infinity``（两者都不是合法 JSON）。
    """
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
    """从宽表抽双色球每期的各奖级注数与单注奖金。

    Returns:
        ``(counts, amounts)`` 两个与 ``df`` 行对齐的列表，内层长度固定为 6（一至六等奖），
        缺失值转成 ``None``。
    """
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
    """从长表 ``dlt_prizes.csv`` 抽大乐透每期的奖级注数与单注奖金。

    Args:
        issues: 该彩种的期号序列；当前未参与过滤，保留以标明调用语境。

    Returns:
        ``(counts, amounts)``：期号（int）→ 该期各奖级注数 / 单注奖金的列表，
        按奖级升序排列。旧期次可能只有部分奖级，因此内层长度不固定。
    """
    raw = pd.read_csv(DATA_DIR / "dlt_prizes.csv", encoding="utf-8-sig")
    # 只保留基本投注：追加奖金在页面里是单独的列，混进来会让奖级与金额错位。
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
    """构造单个彩种嵌入页面的完整载荷。

    Args:
        key: 彩种标识（``"ssq"`` / ``"dlt"``）。

    Returns:
        dict，键为 ``name`` / ``frontPool`` / ``frontPick`` / ``backPool`` / ``backPick`` /
        ``cols``（列顺序）/ ``levels``（奖级文案，键为字符串形式的奖级总数）/
        ``tiers``（该彩种实际出现的最大奖级数）/ ``rows``（逐期数组）。
        每个 ``row`` 的长度等于 ``len(cols)``：期号（int）、日期（``YYYYMMDD`` 整数）、
        号码数组、形态特征、销售额与奖池（元）、一、二等奖注数与金额（缺失为 ``None``）、
        全部奖级的注数与金额数组；大乐透还会在末尾追加 4 个追加投注字段。

    Raises:
        KeyError: ``key`` 未知，或 CSV 缺少某期的 ``p1_count`` 等列。
    """
    data = load(key)
    game = data.game
    df = data.df
    feats = draw_features(data)

    if key == "ssq":
        prize_c, prize_a = _prize_arrays_ssq(df)
        extra = []
    else:
        # 大乐透奖级在长表里；个别期次缺失时回退到 dlt.csv 的一、二等奖列。
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
        # 追加投注字段只在大乐透存在，放在固定列之后；页面按列名取值，不依赖位置。
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
    """构造两种彩种的载荷：``{"ssq": {...}, "dlt": {...}}``。"""
    payload = {key: build_game(key) for key in ("ssq", "dlt")}
    return payload


# 未显式传入 note 时显示的提示文案；显式传 note 的调用方（例如服务端）会覆盖它。
DEFAULT_NOTE = "双击项目根目录的「启动操作台.bat」，或在命令行运行 python scripts/serve.py --open。"


def write_console(port: int = 8777, note: str | None = None, tip: str | None = None) -> Path:
    """生成操作台 HTML；port/note 用于「刷新数据」按钮连本地服务。

    Args:
        port: 本机服务端口，写进 ``__CONFIG__``，页面用它拼接更新请求地址。
        note: 自定义提示文案；``None`` 时用 :data:`DEFAULT_NOTE`。
        tip: 顶部提示；``None`` 时按端口生成“请通过 http://… 打开”。

    Returns:
        生成的 ``output/console.html`` 路径。

    Raises:
        RuntimeError: 模板缺少 ``__DATA__`` / ``__CONFIG__`` 占位符——模板被改动或放错
            目录时立刻失败，而不是悄悄产出空页面。
        OSError: ``output/`` 不可写。

    实现要点：数据里的 ``</`` 会被转义，避免字符串提前闭合内联 ``<script>``；
    数据与配置分别替换，因此可以反复重建同一个文件。
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = build()
    data_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    # 转义 ``</``：否则数据里出现关闭标签时，浏览器会提前结束内联脚本块。
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
