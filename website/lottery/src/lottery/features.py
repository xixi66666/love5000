"""逐期特征工程。

每一期开奖都被展开成一组可解释的"形态"特征，用于：
1) 与精确组合分布做拟合优度检验；
2) 作为回测中的条件变量；
3) 图表展示。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Game
from .data import LotteryData

PRIMES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31)


def ac_value(numbers: np.ndarray) -> int:
    """AC 值：两两差值中不同取值的个数减去 (k−1)。"""
    numbers = np.sort(np.asarray(numbers))
    diff = np.abs(numbers[:, None] - numbers[None, :])
    distinct = len(np.unique(diff[np.triu_indices(len(numbers), 1)]))
    return int(distinct - (len(numbers) - 1))


def max_consecutive(numbers: np.ndarray) -> int:
    numbers = np.sort(np.asarray(numbers))
    best = current = 1
    for gap in np.diff(numbers):
        current = current + 1 if gap == 1 else 1
        best = max(best, current)
    return int(best)


def draw_features(data: LotteryData) -> pd.DataFrame:
    game: Game = data.game
    draw_numbers = [np.flatnonzero(row) + 1 for row in data.front]
    e1, e2 = game.zone_edges

    records = []
    previous = None
    for numbers in draw_numbers:
        tails = np.sort(numbers % 10)
        records.append(
            {
                "sum": int(numbers.sum()),
                "span": int(numbers[-1] - numbers[0]),
                "odd": int((numbers % 2 == 1).sum()),
                "big": int((numbers > game.big_small_split).sum()),
                "consecutive": int((np.diff(numbers) == 1).sum()),
                "max_run": max_consecutive(numbers),
                "ac": ac_value(numbers),
                "prime": int(np.isin(numbers, PRIMES).sum()),
                "tail_distinct": int(1 + (np.diff(tails) > 0).sum()),
                "tail_sum": int(tails.sum()),
                "zone_1": int((numbers <= e1).sum()),
                "zone_2": int(((numbers > e1) & (numbers <= e2)).sum()),
                "zone_3": int((numbers > e2).sum()),
                "repeat": np.nan if previous is None else int(np.intersect1d(numbers, previous).size),
            }
        )
        previous = numbers

    features = pd.DataFrame(records)
    features.insert(0, "date", data.df["date"].to_numpy())
    features.insert(0, "issue", data.df["issue"].to_numpy())
    features["zone_pattern"] = (
        features["zone_1"].astype(str)
        + "|"
        + features["zone_2"].astype(str)
        + "|"
        + features["zone_3"].astype(str)
    )

    if game.back_pick == 1:
        features["back"] = np.argmax(data.back, axis=1) + 1
    else:
        back_numbers = np.array([np.flatnonzero(row) + 1 for row in data.back])
        features["back_sum"] = back_numbers.sum(axis=1)
        features["back_span"] = back_numbers[:, -1] - back_numbers[:, 0]
        features["back_odd"] = (back_numbers % 2 == 1).sum(axis=1)
    return features


def rolling_counts(matrix: np.ndarray, window: int) -> np.ndarray:
    """第 t 行 = 前 window 期（不含 t）内每个号码的出现次数。"""
    n = matrix.shape[0]
    csum = np.vstack([np.zeros((1, matrix.shape[1])), np.cumsum(matrix, axis=0)])
    idx = np.arange(n)
    start = np.maximum(0, idx - window)
    return (csum[idx] - csum[start]).astype(np.int16)


def omission_series(matrix: np.ndarray) -> np.ndarray:
    """第 t 行第 i 列 = 截至第 t 期结束时，号码 i 的当前遗漏（连续未出期数）。"""
    n, p = matrix.shape
    out = np.zeros((n, p), dtype=np.int16)
    counter = np.zeros(p, dtype=np.int16)
    for t in range(n):
        counter = np.where(matrix[t] == 1, 0, counter + 1)
        out[t] = counter
    return out


def current_omission(matrix: np.ndarray) -> np.ndarray:
    """数据末尾的当前遗漏。"""
    return omission_series(matrix)[-1]
