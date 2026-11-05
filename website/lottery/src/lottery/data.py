"""数据加载、校验与基础矩阵。

data/*.csv 由 scripts/fetch_ssq.py、scripts/fetch_dlt.py 抓取并清洗，
本模块只做只读解析，保证后续分析与图表共享同一份干净数据。
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from .config import FIXED_PRIZES, GAMES, Game

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
CACHE_DIR = ROOT / "cache"
OUTPUT_DIR = ROOT / "output"
FIGURE_DIR = OUTPUT_DIR / "figures"


@dataclass
class LotteryData:
    game: Game
    df: pd.DataFrame
    front: np.ndarray  # (n, pool) 0/1
    back: np.ndarray   # (n, pool) 0/1

    @property
    def n(self) -> int:
        return len(self.df)

    @property
    def issues(self) -> np.ndarray:
        return self.df["issue"].to_numpy()

    @property
    def dates(self) -> pd.Series:
        return self.df["date"]

    def front_numbers(self, i: int) -> np.ndarray:
        return np.flatnonzero(self.front[i]) + 1

    def back_numbers(self, i: int) -> np.ndarray:
        return np.flatnonzero(self.back[i]) + 1

    def window(self, start: int, end: int | None = None) -> "LotteryData":
        end = self.n if end is None else end
        return LotteryData(
            game=self.game,
            df=self.df.iloc[start:end].reset_index(drop=True),
            front=self.front[start:end],
            back=self.back[start:end],
        )


def _front_columns(game: Game) -> list[str]:
    prefix = "red" if game.key == "ssq" else "front"
    return [f"{prefix}{i}" for i in range(1, game.front_pick + 1)]


def _back_columns(game: Game) -> list[str]:
    if game.key == "ssq":
        return ["blue"]
    return [f"back{i}" for i in range(1, game.back_pick + 1)]


def _indicator_matrix(numbers: np.ndarray, pool: int) -> np.ndarray:
    matrix = np.zeros((numbers.shape[0], pool), dtype=np.uint8)
    rows = np.repeat(np.arange(numbers.shape[0]), numbers.shape[1])
    matrix[rows, numbers.ravel() - 1] = 1
    return matrix


@lru_cache(maxsize=4)
def load(key: str) -> LotteryData:
    game = GAMES[key]
    path = DATA_DIR / f"{key}.csv"
    df = pd.read_csv(path, encoding="utf-8-sig", parse_dates=["date"])
    df = df.sort_values(["date", "issue"], kind="mergesort").reset_index(drop=True)

    front_cols = _front_columns(game)
    back_cols = _back_columns(game)
    front_numbers = df[front_cols].to_numpy(dtype=np.int16)
    back_numbers = df[back_cols].to_numpy(dtype=np.int16)

    # 基础校验：范围、个数、去重、每行升序
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
    """
    game = GAMES[key]
    df = load(key).df.set_index("issue")
    max_tier = 6 if key == "ssq" else 9
    columns = list(range(1, max_tier + 1))
    table = pd.DataFrame(index=df.index, columns=columns, dtype=float)

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
    """每期派奖总额（元）。用于返奖率分析。"""
    if key == "ssq":
        df = load(key).df.set_index("issue")
        total = pd.Series(0.0, index=df.index)
        for tier in range(1, 7):
            count = df[f"p{tier}_count"].fillna(0)
            amount = df[f"p{tier}_amount"].fillna(0)
            total += count * amount
        return total

    prizes = pd.read_csv(DATA_DIR / f"{key}_prizes.csv", encoding="utf-8-sig")
    prizes = prizes.dropna(subset=["count", "amount"])
    grouped = prizes.groupby("issue").apply(
        lambda g: float((g["count"] * g["amount"]).sum()), include_groups=False
    )
    return grouped.reindex(load(key).df["issue"]).fillna(0.0)


def ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
