"""精确组合分布。

彩票分析里最容易被忽略的一点：很多“形态”（和值、奇偶比、连号、AC 值）
的理论分布并不是正态或均匀分布，而是可以用组合数学**精确**算出来的。
本模块对全部 C(n,k) 个组合做一次完整枚举，得到零假设下的精确分布，
后续所有卡方检验都以它为基准，而不是拍脑袋的“平均分布”。

公开面：
    * :func:`all_combinations`：全部前区组合，形状 ``(C(n,k), k)``；
    * :func:`feature_table` / :class:`FeatureTable`：每个形态取值的精确计数与概率；
    * :func:`hypergeom_pmf`：超几何分布，用于“命中个数”类检验；
    * :func:`tier_probabilities` / :func:`expected_payout`：奖级概率与单注期望回报。

副作用：首次调用会把枚举结果写入 ``cache/combos_<key>_<n>_<k>.npy``、把形态计数写入
``cache/features_<key>.json``，之后直接读缓存。双色球 1,107,568 个组合、大乐透 324,632 个
组合，全枚举在秒级完成，但缓存文件较大，属于可随时删除的重建型数据。
"""

from __future__ import annotations

import json
from functools import lru_cache
from math import comb

import numpy as np

from .config import PRIZE_TIER, Game
from .data import CACHE_DIR

# 1..35 范围内的全部素数；两种游戏的号码池上限是 33 / 35，因此这张表对两者都完整。
PRIMES = np.array([2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31])


def _combo_path(game: Game):
    """组合缓存的落盘路径；文件名带池大小与选号个数，换规则后不会误读旧缓存。"""
    return CACHE_DIR / f"combos_{game.key}_{game.front_pool}_{game.front_pick}.npy"


@lru_cache(maxsize=4)
def all_combinations(game: Game) -> np.ndarray:
    """全部前区组合，按升序排列，形状 (C(n,k), k)，int8。

    号码 1..n，每个组合内部升序、组合之间按字典序；``int8`` 足够表示 1..35。
    命中缓存时直接 :func:`numpy.load`，不重复枚举。

    Args:
        game: 彩种规则。它同时是 ``lru_cache`` 的键，因此必须可哈希。

    Returns:
        组合矩阵；缓存是进程级共享的，调用方不要原地修改。

    副作用：缓存缺失时先按 65536 行一块写进缓冲，再一次落盘到 ``cache/``。
    """
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
    """组合枚举的唯一入口。

    单独包一层，便于在不改调用方的前提下替换枚举实现（例如按位生成）；
    当前直接转调 :func:`itertools.combinations`，返回值是迭代器。
    """
    from itertools import combinations

    return combinations(iterable, k)


def _ac_values(combos: np.ndarray) -> np.ndarray:
    """批量计算每个组合的 AC 值 = 互不相同的两两差值个数 − (k−1)。

    Args:
        combos: ``(m, k)`` 的升序组合矩阵。

    Returns:
        长度 m 的 ``int16`` 数组。

    实现按 2 万行分块，避免一次算出 ``m × k(k−1)/2`` 的差值矩阵把内存打满：
    块内先把差值排序，再用“相邻差大于 0”统计不同取值的个数。
    """
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
    """最长连号长度（单号视为 1）。

    对已升序的组合逐列扫描：相邻列差为 1 则当前连号长度加 1，否则归零，
    全程取最大值后再加 1（单个号码本身算长度 1）。
    """
    m, k = combos.shape
    close = np.diff(combos, axis=1) == 1
    best = np.zeros(m, dtype=np.int16)
    current = np.zeros(m, dtype=np.int16)
    for j in range(k - 1):
        current = np.where(close[:, j], current + 1, 0)
        best = np.maximum(best, current)
    return best + 1


def _zone_ids(combos: np.ndarray, game: Game) -> np.ndarray:
    """把号码映射成三区编号 0/1/2（0 表示一区），边界取自 :attr:`Game.zone_edges`。"""
    e1, e2 = game.zone_edges
    ids = np.zeros_like(combos, dtype=np.int8)
    ids[combos > e1] = 1
    ids[combos > e2] = 2
    return ids


def _prime_mask(values: np.ndarray) -> np.ndarray:
    """逐号码判定是否为素数；1..35 之外的取值一律判为非素数。"""
    return np.isin(values, PRIMES)


def _features(combos: np.ndarray, game: Game) -> dict[str, np.ndarray]:
    """对全部组合批量计算形态特征。

    Args:
        combos: ``(m, k)`` 的升序组合矩阵。
        game: 彩种规则，用于三区边界与大小分界。

    Returns:
        特征名到 ``(m,)`` 数组的映射，键与 :func:`feature_table` 写进 JSON 的 ``counts``
        一致：``sum`` / ``span`` / ``odd`` / ``big`` / ``consecutive`` / ``max_run`` /
        ``ac`` / ``prime`` / ``tail_distinct`` / ``tail_sum`` / ``zone_1`` / ``zone_2`` /
        ``zone_3``。全部是整数计数或求和，不含浮点，便于无损写入 JSON。
    """
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
    """把 numpy 整数与号码对元组收敛成 JSON 可写的原生类型。

    ``np.integer`` 转 ``int``，元组转成 ``"a|b"`` 形式的字符串。
    当前缓存写入走字典推导，并没有调用本函数，保留它是作为缓存序列化工具。
    """
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, tuple):
        return "|".join(str(int(v)) for v in value)
    return value


@lru_cache(maxsize=4)
def feature_table(game: Game) -> "FeatureTable":
    """每个形态取值的精确计数表，首次计算后写入 JSON 缓存。

    除 :func:`_features` 的 13 个单变量特征外，还额外统计 ``zone_pattern``：
    三区个数被编码成 ``zone_1*64 + zone_2*8 + zone_3``，再还原成 ``"a|b|c"`` 字符串键。

    Args:
        game: 彩种规则（同时是缓存键）。

    Returns:
        :class:`FeatureTable`，其 ``total`` 等于该彩种的前区组合总数。

    副作用：缓存缺失时写 ``cache/features_<key>.json``（UTF-8、不转义中文），
    因此第一次调用会比后续调用慢，但结果与缓存命中时完全一致。
    """
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
    """形态取值的精确计数容器，也就是零假设下的“真值表”。

    计数以字符串为键（JSON 无法直接存整数键），因此任何查表都要先 ``str(value)``。

    Args:
        game: 彩种规则。
        counts: 形态名 → {取值字符串: 组合数}。
        total: 组合总数，等于任一形态所有计数之和。
    """

    def __init__(self, game: Game, counts: dict[str, dict[str, int]], total: int):
        """保存规则、计数表与组合总数；各参数含义见类文档。"""
        self.game = game
        self.counts = counts
        self.total = total

    def prob(self, feature: str, value) -> float:
        """某个形态取某个值的精确概率（0–1）；表中没有的取值返回 0.0。"""
        key = str(value)
        return self.counts[feature].get(key, 0) / self.total

    def support(self, feature: str) -> list:
        """该形态所有可能取值（字符串）的列表，顺序即 JSON 中的插入顺序。"""
        return list(self.counts[feature])

    def pmf(self, feature: str) -> tuple[np.ndarray, np.ndarray]:
        """形态的概率质量函数，按取值升序排列。

        Returns:
            ``(values, probs)``：``values`` 为浮点取值，``probs`` 为精确概率（和为 1）。
            复合键（如三区比 ``"2|2|2"``）无法转成数值，对应 ``values`` 为 ``nan``；
            :func:`numpy.argsort` 会把 ``nan`` 排在末尾，调用方画图前需自行过滤。
        """
        items = self.counts[feature]
        keys = list(items)
        values = np.array([float(k) if "|" not in k else np.nan for k in keys])
        probs = np.array([v / self.total for v in items.values()])
        order = np.argsort(values, kind="stable")
        return values[order], probs[order]


def hypergeom_pmf(population: int, successes: int, draws: int) -> np.ndarray:
    """超几何分布：从 population 中不放回抽 draws 个，命中 successes 中 k 个的概率。

    Args:
        population: 号码池大小 N。
        successes: 被视为“命中”的号码个数，通常等于自己选中的个数。
        draws: 不放回抽取的个数。

    Returns:
        下标即命中个数 k 的一维数组，长度为 ``min(draws, successes) + 1``，
        元素为概率（0–1），整体求和为 1。
    """
    ks = np.arange(0, min(draws, successes) + 1)
    denom = comb(population, draws)
    return np.array([comb(successes, k) * comb(population - successes, draws - k) / denom for k in ks])


@lru_cache(maxsize=4)
def tier_probabilities(game: Game) -> np.ndarray:
    """各奖级中奖概率，索引 0 表示未中奖。

    对前区命中数 f 与后区命中数 b 的两条超几何分布做笛卡尔积，
    把联合概率累加到 :data:`lottery.config.PRIZE_TIER` 给出的奖级上。

    Returns:
        长度 10 的数组：``[0]`` 未中奖、``[1]`` 一等奖……；只有浮点舍入导致总和
        偏离 1 时才会做一次归一化，正常路径不改动原值。
    """
    front_p = hypergeom_pmf(game.front_pool, game.front_pick, game.front_pick)
    back_p = hypergeom_pmf(game.back_pool, game.back_pick, game.back_pick)
    tiers = np.zeros(10)
    tier_fn = PRIZE_TIER[game.key]
    for f, pf in enumerate(front_p):
        for b, pb in enumerate(back_p):
            tiers[tier_fn(f, b)] += pf * pb
    return tiers / tiers.sum() if abs(tiers.sum() - 1) > 1e-9 else tiers


def expected_payout(game: Game, amounts: np.ndarray) -> float:
    """给定当期各奖级单注奖金，计算一注（2 元）的期望回报。

    Args:
        game: 彩种规则。
        amounts: 长度等于最大奖级的数组，``amounts[t-1]`` 是第 t 等奖单注奖金（元），
            通常直接取 :func:`lottery.data.prize_amounts` 的某一行。

    Returns:
        单注期望回报（元/注），不含追加投注；正常情况下显著低于 2 元票价。
    """
    tiers = tier_probabilities(game)
    return float(sum(tiers[t] * amounts[t - 1] for t in range(1, len(amounts) + 1)))
