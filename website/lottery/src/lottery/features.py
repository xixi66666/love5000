"""逐期特征工程。

每一期开奖都被展开成一组可解释的“形态”特征，用于：
1) 与精确组合分布做拟合优度检验（:mod:`lottery.tests`）；
2) 作为回测中的条件变量（:mod:`lottery.models`）；
3) 图表展示（:mod:`lottery.charts`）。

特征口径与单位（前区/红球；后区见 :func:`draw_features`）：
    * ``sum`` 和值、``span`` 跨度、``tail_sum`` 尾数和：号码之和，无量纲；
    * ``odd`` 奇数个数、``big`` 大号个数、``prime`` 素数个数：计数，单位“个”；
    * ``consecutive`` 相邻连号对数、``max_run`` 最长连号长度、``ac`` AC 值：计数；
    * ``tail_distinct`` 不同尾数个数、``zone_1``…``zone_3`` 三区个数、``zone_pattern`` 三区比；
    * ``repeat`` 与上一期的重号个数（首期为 ``NaN``，因为不存在上一期）。

本模块只做纯计算，不读写文件；所有特征都是对“已开奖号码”的描述，
不含任何关于下一期的信息。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Game
from .data import LotteryData

# 与 combinatorics.PRIMES 内容相同但独立定义：本模块用元组做 np.isin 判定，
# 组合枚举模块用 ndarray 做向量化。两处必须同步修改，否则特征与理论分布会不一致。
PRIMES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31)


def ac_value(numbers: np.ndarray) -> int:
    """AC 值：两两差值中不同取值的个数减去 (k−1)。

    这是彩民圈常用的“号码离散度”指标：连号越多、差值重复越多，AC 值越小。
    由于重复差值不重复计数，k 个号码的理论最大值是 ``C(k,2) − (k−1)``。

    Args:
        numbers: 一期的号码，顺序无关（函数内部先排序）。

    Returns:
        非负整数。双色球（k=6）最大 14，大乐透（k=5）最大 9。
    """
    numbers = np.sort(np.asarray(numbers))
    diff = np.abs(numbers[:, None] - numbers[None, :])
    distinct = len(np.unique(diff[np.triu_indices(len(numbers), 1)]))
    return int(distinct - (len(numbers) - 1))


def max_consecutive(numbers: np.ndarray) -> int:
    """最长连号长度（单号视为 1）。

    Args:
        numbers: 一期的号码，顺序无关（函数内部先排序）。

    Returns:
        最长连续整数段的长度，例如 ``[3, 4, 5, 9]`` 返回 3。
    """
    numbers = np.sort(np.asarray(numbers))
    best = current = 1
    for gap in np.diff(numbers):
        current = current + 1 if gap == 1 else 1
        best = max(best, current)
    return int(best)


def draw_features(data: LotteryData) -> pd.DataFrame:
    """把一个彩种的全部开奖展开成逐期特征表。

    Args:
        data: 已加载并校验的开奖数据。

    Returns:
        与 ``data.df`` 行对齐的 DataFrame：前两列是 ``issue`` / ``date``，
        其后是模块文档列出的形态特征与 ``zone_pattern``（形如 ``"2|2|2"`` 的三区比）。
        后区列按玩法不同：双色球（``back_pick == 1``）给 ``back``（蓝球号码本身），
        大乐透给 ``back_sum`` / ``back_span`` / ``back_odd``。
        ``repeat`` 首期为 ``NaN``，其余为与上一期的重号个数。
    """
    game: Game = data.game
    draw_numbers = [np.flatnonzero(row) + 1 for row in data.front]
    e1, e2 = game.zone_edges

    records = []
    # previous 保存上一期号码，用于计算 repeat；首期没有上一期，记为 NaN。
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
    """第 t 行 = 前 window 期（不含 t）内每个号码的出现次数。

    严格因果：第 t 行的窗口是 ``[t-window, t)``，不含第 t 期本身，
    因此可以直接用于“在第 t 期开奖前选号”的策略，不会泄漏当期结果。

    Returns:
        ``int16`` 矩阵，形状与 ``matrix`` 相同；窗口不足时按实际可用期数计算。
    """
    n = matrix.shape[0]
    csum = np.vstack([np.zeros((1, matrix.shape[1])), np.cumsum(matrix, axis=0)])
    idx = np.arange(n)
    start = np.maximum(0, idx - window)
    return (csum[idx] - csum[start]).astype(np.int16)


def omission_series(matrix: np.ndarray) -> np.ndarray:
    """第 t 行第 i 列 = 截至第 t 期结束时，号码 i 的当前遗漏（连续未出期数）。

    注意“截至第 t 期结束”意味着第 t 行**包含**第 t 期的结果；若要在第 t 期开奖前
    选号，必须用第 ``t-1`` 行（见 :class:`lottery.models.ColdStrategy`）。

    Returns:
        ``(n, pool)`` 的 ``int16`` 矩阵，列 i 对应号码 ``i + 1``，单位为期。
    """
    n, p = matrix.shape
    out = np.zeros((n, p), dtype=np.int16)
    counter = np.zeros(p, dtype=np.int16)
    for t in range(n):
        counter = np.where(matrix[t] == 1, 0, counter + 1)
        out[t] = counter
    return out


def current_omission(matrix: np.ndarray) -> np.ndarray:
    """数据末尾（最新一期开奖后）的当前遗漏。

    Returns:
        长度等于号码池大小的一维 ``int16`` 数组，单位期；数值 0 表示最新一期刚开出。
    """
    return omission_series(matrix)[-1]
