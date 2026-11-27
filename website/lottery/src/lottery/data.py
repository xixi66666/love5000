"""数据加载、校验与基础矩阵。

``data/*.csv`` 由 ``scripts/fetch_ssq.py``、``scripts/fetch_dlt.py`` 抓取并清洗，
本模块只做只读解析，保证后续分析与图表共享同一份干净数据。官方开奖 CSV 的追加
只发生在 ``scripts/update_daily.py``，且每次写入前都会备份到 ``data/backup/<时间戳>/``；
本模块不写回 CSV，只会在 ``cache/`` 与 ``output/`` 下创建目录。

输入数据形状（两种彩种共用同一套列名风格）：
    * 公共列：``issue``（期号，整数）、``date``（开奖日期）、``sales``（销售额，元）、
      ``pool``（奖池，元）、``p<n>_count`` / ``p<n>_amount``（第 n 等奖注数与单注奖金，元）；
    * 双色球号码列：``red1``…``red6``、``blue``；
    * 大乐透号码列：``front1``…``front5``、``back1``…``back2``，以及追加投注的
      ``p1_add_count`` / ``p1_add_amount`` 等列。

公开面：:class:`LotteryData`（数据 + 0/1 指示矩阵）、:func:`load`、
:func:`prize_amounts`、:func:`total_prize_payout`、:func:`ensure_dirs` 与几个目录常量。

失败行为：CSV 缺失抛 :class:`FileNotFoundError`，彩种 key 未知抛 :class:`KeyError`，
号码越界、每期个数不对或同注重号会触发 ``assert``——数据被污染时宁可中断，
也不要带着坏数据去跑检验和回测。
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from .config import FIXED_PRIZES, GAMES, Game

# ROOT 指向 website/lottery（本文件在 src/lottery 下，向上三层），
# 所有路径都相对它解析，因此从任意工作目录启动都能找到 data/ 与 output/。
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
CACHE_DIR = ROOT / "cache"
OUTPUT_DIR = ROOT / "output"
FIGURE_DIR = OUTPUT_DIR / "figures"


@dataclass
class LotteryData:
    """一种彩票的只读数据集（已按 date、issue 升序排好）。

    Attributes:
        game: 彩种规则。
        df: 原始明细，保留 ``issue`` / ``date`` / ``sales`` / ``pool`` / 奖级列，
            并额外补出 ``issue_str``（字符串期号）与 ``draw_no``（1 起连续期序）。
        front: ``(n, front_pool)`` 的 0/1 ``uint8`` 指示矩阵；第 i 行是第 i 期，
            列 j 对应号码 ``j + 1``。
        back: 同上，形状为 ``(n, back_pool)``。
    """

    game: Game
    df: pd.DataFrame
    front: np.ndarray  # (n, pool) 0/1
    back: np.ndarray   # (n, pool) 0/1

    @property
    def n(self) -> int:
        """已加载的期数。"""
        return len(self.df)

    @property
    def issues(self) -> np.ndarray:
        """期号数组（整数，按时间升序）。"""
        return self.df["issue"].to_numpy()

    @property
    def dates(self) -> pd.Series:
        """开奖日期序列（dtype 为 ``datetime64``）。"""
        return self.df["date"]

    def front_numbers(self, i: int) -> np.ndarray:
        """第 i 期的前区/红球号码，返回 1 起的升序数组。

        Args:
            i: 行下标（0 起）；越界时由 numpy 抛 :class:`IndexError`。
        """
        return np.flatnonzero(self.front[i]) + 1

    def back_numbers(self, i: int) -> np.ndarray:
        """第 i 期的后区/蓝球号码，返回 1 起的升序数组。"""
        return np.flatnonzero(self.back[i]) + 1

    def window(self, start: int, end: int | None = None) -> "LotteryData":
        """取 ``[start, end)`` 这段期次，返回新的 :class:`LotteryData`。

        只做数组切片与 ``df`` 视图，不重新读 CSV；``df`` 的索引会被重置为 0，
        但 ``draw_no`` 仍保留原始期序。
        """
        end = self.n if end is None else end
        return LotteryData(
            game=self.game,
            df=self.df.iloc[start:end].reset_index(drop=True),
            front=self.front[start:end],
            back=self.back[start:end],
        )


def _front_columns(game: Game) -> list[str]:
    """前区号码在 CSV 中的列名：双色球是 ``red1``…``red6``，大乐透是 ``front1``…``front5``。"""
    prefix = "red" if game.key == "ssq" else "front"
    return [f"{prefix}{i}" for i in range(1, game.front_pick + 1)]


def _back_columns(game: Game) -> list[str]:
    """后区号码列名：双色球只有一个 ``blue``，大乐透是 ``back1`` / ``back2``。"""
    if game.key == "ssq":
        return ["blue"]
    return [f"back{i}" for i in range(1, game.back_pick + 1)]


def _indicator_matrix(numbers: np.ndarray, pool: int) -> np.ndarray:
    """把 ``(n, k)`` 的 1 起号码矩阵展开成 ``(n, pool)`` 的 0/1 指示矩阵。

    Args:
        numbers: 每行是一期的号码，取值 1..pool。
        pool: 号码池大小。

    Returns:
        ``uint8`` 矩阵，列 j 对应号码 ``j + 1``。同一行出现重复号码会互相覆盖，
        但 :func:`load` 已先校验每期号码互不相同。
    """
    matrix = np.zeros((numbers.shape[0], pool), dtype=np.uint8)
    rows = np.repeat(np.arange(numbers.shape[0]), numbers.shape[1])
    matrix[rows, numbers.ravel() - 1] = 1
    return matrix


@lru_cache(maxsize=4)
def load(key: str) -> LotteryData:
    """只读加载并校验一个彩种的全部历史开奖。

    结果带 ``lru_cache``：同一进程内重复调用返回同一个对象，
    **调用方不得原地修改**返回的 ``df`` / ``front`` / ``back``；需要子集时用
    :meth:`LotteryData.window`。

    Args:
        key: 彩种标识，``"ssq"`` 或 ``"dlt"``。

    Returns:
        :class:`LotteryData`；行已按 ``date``、``issue`` 稳定排序（``mergesort``
        保证同日期多期时仍保持 CSV 原始顺序）。

    Raises:
        KeyError: ``key`` 不在 :data:`lottery.config.GAMES` 中。
        FileNotFoundError: ``data/<key>.csv`` 不存在。
        AssertionError: 号码越界、每期个数不对或同注重号——说明数据被污染。
    """
    game = GAMES[key]
    path = DATA_DIR / f"{key}.csv"
    df = pd.read_csv(path, encoding="utf-8-sig", parse_dates=["date"])
    df = df.sort_values(["date", "issue"], kind="mergesort").reset_index(drop=True)

    front_cols = _front_columns(game)
    back_cols = _back_columns(game)
    front_numbers = df[front_cols].to_numpy(dtype=np.int16)
    back_numbers = df[back_cols].to_numpy(dtype=np.int16)

    # 基础校验：号码范围、每期个数、同注去重；任一条不满足说明数据已被污染，直接中断。
    assert front_numbers.min() >= 1 and front_numbers.max() <= game.front_pool
    assert back_numbers.min() >= 1 and back_numbers.max() <= game.back_pool
    for row in front_numbers:
        assert len(np.unique(row)) == game.front_pick
    for row in back_numbers:
        assert len(np.unique(row)) == game.back_pick

    front = _indicator_matrix(front_numbers, game.front_pool)
    back = _indicator_matrix(back_numbers, game.back_pool)

    df["issue_str"] = df["issue"].astype(str)
    df["draw_no"] = np.arange(1, len(df) + 1)
    return LotteryData(game=game, df=df, front=front, back=back)


@lru_cache(maxsize=4)
def prize_amounts(key: str) -> pd.DataFrame:
    """每期各奖级单注奖金（基本投注，不含追加）。

    一、二等奖按当期官方金额浮动；三至九等奖为固定奖金。
    索引为 issue，列为奖级 1..max_tier。

    Args:
        key: 彩种标识。

    Returns:
        ``float`` 的 DataFrame（index=issue、columns=1..6 或 1..9），单位元/注。
        官方字段极少数期次缺失时用该奖级的中位数补齐，因此结果不含 NaN，
        可以直接参与期望值与回测结算。

    Raises:
        KeyError: 彩种未知，或 CSV 缺少对应的 ``p<n>_amount`` 列。
    """
    game = GAMES[key]
    df = load(key).df.set_index("issue")
    max_tier = 6 if key == "ssq" else 9
    columns = list(range(1, max_tier + 1))
    table = pd.DataFrame(index=df.index, columns=columns, dtype=float)

    # 固定奖级直接写常量，浮动奖级沿用官方逐期金额。
    for tier in columns:
        fixed = FIXED_PRIZES[key].get(tier)
        if fixed is not None:
            table[tier] = float(fixed)
        else:
            table[tier] = df[f"p{tier}_amount"].astype(float)

    # 极少数期次一、二等奖金额缺失：用奖级中位数补齐，避免期望值出现 NaN
    for tier in columns:
        if table[tier].isna().any():
            table[tier] = table[tier].fillna(table[tier].median())
    return table


def total_prize_payout(key: str) -> pd.Series:
    """每期派奖总额（元），用于返奖率分析。

    Args:
        key: 彩种标识。

    Returns:
        以 issue 为索引的 Series，单位元；按 ``load(key)`` 的期号顺序对齐，
        缺失期次填 0。两种彩种的奖级存放方式不同，但结果口径一致：
        都是“该期各奖级注数 × 单注奖金”的求和。

    Raises:
        KeyError: 彩种未知或 CSV 缺少奖级列。
        FileNotFoundError: 大乐透缺少 ``dlt_prizes.csv``。
    """
    if key == "ssq":
        df = load(key).df.set_index("issue")
        total = pd.Series(0.0, index=df.index)
        for tier in range(1, 7):
            count = df[f"p{tier}_count"].fillna(0)
            amount = df[f"p{tier}_amount"].fillna(0)
            total += count * amount
        return total

    # 大乐透的奖级摊在长表 dlt_prizes.csv（每期每奖级一行），先过滤缺值再按 issue 汇总。
    prizes = pd.read_csv(DATA_DIR / f"{key}_prizes.csv", encoding="utf-8-sig")
    prizes = prizes.dropna(subset=["count", "amount"])
    grouped = prizes.groupby("issue").apply(
        lambda g: float((g["count"] * g["amount"]).sum()), include_groups=False
    )
    return grouped.reindex(load(key).df["issue"]).fillna(0.0)


def ensure_dirs() -> None:
    """确保 ``output/``、``output/figures/`` 与 ``cache/`` 存在（幂等）。

    供命令行入口在出图、写报告前调用；本包其余函数各自负责自己的目录创建，
    因此单独 import 并调用分析函数时不需要先调它。
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
