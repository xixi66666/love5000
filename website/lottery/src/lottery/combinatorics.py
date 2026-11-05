"""精确组合分布。

彩票分析里最容易被忽略的一点：很多"形态"（和值、奇偶比、连号、AC 值）
的理论分布并不是正态或均匀分布，而是可以用组合数学**精确**算出来的。
本模块对全部 C(n,k) 个组合做一次完整枚举，得到零假设下的精确分布，
后续所有卡方检验都以它为基准，而不是拍脑袋的"平均分布"。
"""

from __future__ import annotations

import json
from functools import lru_cache
from math import comb

import numpy as np

from .config import PRIZE_TIER, Game
from .data import CACHE_DIR

PRIMES = np.array([2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31])


def _combo_path(game: Game):
    return CACHE_DIR / f"combos_{game.key}_{game.front_pool}_{game.front_pick}.npy"


@lru_cache(maxsize=4)
def all_combinations(game: Game) -> np.ndarray:
    """全部前区组合，按升序排列，形状 (C(n,k), k)，int8。"""
    path = _combo_path(game)
    if path.exists():
        return np.load(path)

    n, k = game.front_pool, game.front_pick
    total = comb(n, k)
    out = np.empty((total, k), dtype=np.int8)
    buffer = np.empty((1 << 16, k), dtype=np.int8)
    size = 0
    row = 0
    for combo in _combinations(range(1, n + 1), k):
        buffer[size] = combo
        size += 1
        if size == len(buffer):
            out[row : row + size] = buffer
            row += size
            size = 0
    if size:
        out[row : row + size] = buffer[:size]
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, out)
    return out


def _combinations(iterable, k):
    """itertools.combinations 的本地包装，便于未来替换实现。"""
    from itertools import combinations

    return combinations(iterable, k)


def _ac_values(combos: np.ndarray) -> np.ndarray:
    """AC 值 = 互不相同的两两差值个数 − (k−1)。"""
    m, k = combos.shape
    out = np.empty(m, dtype=np.int16)
    iu, ju = np.triu_indices(k, 1)
    step = 20_000
    for start in range(0, m, step):
        block = combos[start : start + step].astype(np.int16)
        diff = block[:, ju] - block[:, iu]  # (B, k*(k-1)/2)
        diff.sort(axis=1)
        distinct = 1 + (np.diff(diff, axis=1) > 0).sum(axis=1)
        out[start : start + len(block)] = distinct - (k - 1)
    return out


def _max_run(combos: np.ndarray) -> np.ndarray:
    """最长连号长度（单号视为 1）。"""
    m, k = combos.shape
    close = np.diff(combos, axis=1) == 1
    best = np.zeros(m, dtype=np.int16)
    current = np.zeros(m, dtype=np.int16)
    for j in range(k - 1):
        current = np.where(close[:, j], current + 1, 0)
        best = np.maximum(best, current)
    return best + 1


def _zone_ids(combos: np.ndarray, game: Game) -> np.ndarray:
    e1, e2 = game.zone_edges
    ids = np.zeros_like(combos, dtype=np.int8)
    ids[combos > e1] = 1
    ids[combos > e2] = 2
    return ids


def _prime_mask(values: np.ndarray) -> np.ndarray:
    return np.isin(values, PRIMES)


def _features(combos: np.ndarray, game: Game) -> dict[str, np.ndarray]:
    zones = _zone_ids(combos, game)
    tails = combos % 10
    tail_sorted = np.sort(tails, axis=1)
    return {
        "sum": combos.sum(axis=1).astype(np.int16),
        "span": (combos[:, -1] - combos[:, 0]).astype(np.int16),
        "odd": (combos % 2 == 1).sum(axis=1).astype(np.int8),
        "big": (combos > game.big_small_split).sum(axis=1).astype(np.int8),
        "consecutive": (np.diff(combos, axis=1) == 1).sum(axis=1).astype(np.int8),
        "max_run": _max_run(combos),
        "ac": _ac_values(combos),
        "prime": _prime_mask(combos).sum(axis=1).astype(np.int8),
        "tail_distinct": (1 + (np.diff(tail_sorted, axis=1) > 0).sum(axis=1)).astype(np.int8),
        "tail_sum": tails.sum(axis=1).astype(np.int16),
        "zone_1": (zones == 0).sum(axis=1).astype(np.int8),
        "zone_2": (zones == 1).sum(axis=1).astype(np.int8),
        "zone_3": (zones == 2).sum(axis=1).astype(np.int8),
    }


def _serialise(value):
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, tuple):
        return "|".join(str(int(v)) for v in value)
    return value


@lru_cache(maxsize=4)
def feature_table(game: Game) -> "FeatureTable":
    path = CACHE_DIR / f"features_{game.key}.json"
    combos = all_combinations(game)
    if path.exists():
        raw = json.loads(path.read_text(encoding="utf-8"))
        return FeatureTable(game=game, counts=raw["counts"], total=raw["total"])

    arrays = _features(combos, game)
    counts: dict[str, dict[str, int]] = {}
    for name, values in arrays.items():
        uniq, cnt = np.unique(values, return_counts=True)
        counts[name] = {str(int(u)): int(c) for u, c in zip(uniq, cnt)}

    zone_code = (
        arrays["zone_1"].astype(np.int16) * 64
        + arrays["zone_2"].astype(np.int16) * 8
        + arrays["zone_3"].astype(np.int16)
    )
    uniq, cnt = np.unique(zone_code, return_counts=True)
    counts["zone_pattern"] = {
        f"{u // 64}|{(u % 64) // 8}|{u % 8}": int(c) for u, c in zip(uniq, cnt)
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"counts": counts, "total": int(len(combos))}, ensure_ascii=False),
        encoding="utf-8",
    )
    return FeatureTable(game=game, counts=counts, total=len(combos))


class FeatureTable:
    def __init__(self, game: Game, counts: dict[str, dict[str, int]], total: int):
        self.game = game
        self.counts = counts
        self.total = total

    def prob(self, feature: str, value) -> float:
        key = str(value)
        return self.counts[feature].get(key, 0) / self.total

    def support(self, feature: str) -> list:
        return list(self.counts[feature])

    def pmf(self, feature: str) -> tuple[np.ndarray, np.ndarray]:
        items = self.counts[feature]
        keys = list(items)
        values = np.array([float(k) if "|" not in k else np.nan for k in keys])
        probs = np.array([v / self.total for v in items.values()])
        order = np.argsort(values, kind="stable")
        return values[order], probs[order]


def hypergeom_pmf(population: int, successes: int, draws: int) -> np.ndarray:
    """超几何分布：从 population 中不放回抽 draws 个，命中 successes 中 k 个的概率。"""
    ks = np.arange(0, min(draws, successes) + 1)
    denom = comb(population, draws)
    return np.array([comb(successes, k) * comb(population - successes, draws - k) / denom for k in ks])


@lru_cache(maxsize=4)
def tier_probabilities(game: Game) -> np.ndarray:
    """各奖级中奖概率，索引 0 表示未中奖。"""
    front_p = hypergeom_pmf(game.front_pool, game.front_pick, game.front_pick)
    back_p = hypergeom_pmf(game.back_pool, game.back_pick, game.back_pick)
    tiers = np.zeros(10)
    tier_fn = PRIZE_TIER[game.key]
    for f, pf in enumerate(front_p):
        for b, pb in enumerate(back_p):
            tiers[tier_fn(f, b)] += pf * pb
    return tiers / tiers.sum() if abs(tiers.sum() - 1) > 1e-9 else tiers


def expected_payout(game: Game, amounts: np.ndarray) -> float:
    """给定当期各奖级单注奖金，计算一注（2 元）的期望回报。"""
    tiers = tier_probabilities(game)
    return float(sum(tiers[t] * amounts[t - 1] for t in range(1, len(amounts) + 1)))
