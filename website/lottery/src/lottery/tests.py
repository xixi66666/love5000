"""统计检验层。

核心原则：
* 每个检验都对应一个可证伪的零假设（通常是"开奖等价于均匀随机抽样"）；
* 形态类检验使用**精确组合分布**作为期望，而不是正态近似；
* 大量检验必然产生假阳性，因此统一做 Benjamini–Hochberg FDR 校正；
* 对号码对共现这类统计量分布未知的检验，用蒙特卡洛置换检验。

输出统一为 TestResult 列表，便于汇总成表和图。
"""

from __future__ import annotations

from dataclasses import dataclass
from math import comb

import numpy as np
import pandas as pd
from scipy import stats

from .combinatorics import feature_table, hypergeom_pmf
from .config import Game
from .data import LotteryData
from .features import current_omission, draw_features

N_PERMUTATIONS = 300


@dataclass
class TestResult:
    game: str
    category: str
    name: str
    statistic: float | None
    dof: float | None
    pvalue: float
    note: str = ""

    def as_row(self) -> dict:
        return {
            "game": self.game,
            "category": self.category,
            "test": self.name,
            "statistic": self.statistic,
            "dof": self.dof,
            "p_value": self.pvalue,
            "note": self.note,
        }


def fdr_bh(pvalues: np.ndarray) -> np.ndarray:
    """Benjamini–Hochberg 校正后的 q 值。"""
    p = np.asarray(pvalues, dtype=float)
    n = len(p)
    order = np.argsort(p)
    ranked = p[order]
    q = ranked * n / np.arange(1, n + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.clip(q, 0, 1)
    return out


def chi2_binned(observed: np.ndarray, expected_prob: np.ndarray) -> tuple[float, int, float, int]:
    """把期望频数过小的尾部类别合并后再做卡方检验。

    observed 与 expected_prob 按同一顺序排列；返回 (统计量, 自由度, p 值, 合并后类别数)。
    """
    observed = np.asarray(observed, dtype=float)
    total = observed.sum()
    expected = np.asarray(expected_prob, dtype=float) * total

    order = np.argsort(expected)  # 从小到大，先合并稀疏尾部
    bins_obs: list[float] = []
    bins_exp: list[float] = []
    acc_obs = acc_exp = 0.0
    for idx in order:
        acc_obs += observed[idx]
        acc_exp += expected[idx]
        if acc_exp >= 5.0:
            bins_obs.append(acc_obs)
            bins_exp.append(acc_exp)
            acc_obs = acc_exp = 0.0
    if acc_exp > 0 or acc_obs > 0:
        if bins_exp:
            bins_obs[-1] += acc_obs
            bins_exp[-1] += acc_exp
        else:
            bins_obs.append(acc_obs)
            bins_exp.append(acc_exp)

    bins_obs_arr = np.array(bins_obs)
    bins_exp_arr = np.array(bins_exp)
    stat = float(((bins_obs_arr - bins_exp_arr) ** 2 / bins_exp_arr).sum())
    dof = max(len(bins_obs_arr) - 1, 1)
    pvalue = float(stats.chi2.sf(stat, dof))
    return stat, dof, pvalue, len(bins_obs_arr)


def number_uniformity(matrix: np.ndarray, label: str, game: str) -> tuple[TestResult, np.ndarray, np.ndarray]:
    n, pool = matrix.shape
    counts = matrix.sum(axis=0).astype(float)
    p = matrix.sum() / (n * pool)
    expected = n * p
    stat = float(((counts - expected) ** 2 / expected).sum())
    dof = pool - 1
    pvalue = float(stats.chi2.sf(stat, dof))
    residuals = (counts - expected) / np.sqrt(expected * (1 - p))
    result = TestResult(
        game=game,
        category="边际均匀性",
        name=f"{label}号码出现频数 χ²",
        statistic=stat,
        dof=dof,
        pvalue=pvalue,
        note=f"{pool} 个号码，期望 {expected:.1f} 次",
    )
    return result, counts, residuals


def pvalue_qq(pvalues: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """把 p 值排序后与 Uniform(0,1) 分位数对照。"""
    p = np.sort(np.asarray(pvalues, dtype=float))
    m = len(p)
    expected = (np.arange(1, m + 1) - 0.5) / m
    return expected, p


def ljung_box(series: np.ndarray, lags: int = 12) -> tuple[float, int, float]:
    x = np.asarray(series, dtype=float)
    x = x - x.mean()
    n = len(x)
    denom = np.dot(x, x)
    q = 0.0
    for k in range(1, lags + 1):
        r = np.dot(x[:-k], x[k:]) / denom
        q += r * r / (n - k)
    q *= n * (n + 2)
    dof = lags
    return float(q), dof, float(stats.chi2.sf(q, dof))


def runs_test(series: np.ndarray) -> tuple[float, float]:
    """Wald–Wolfowitz 游程检验（以中位数为界）。"""
    x = np.asarray(series, dtype=float)
    binary = x > np.median(x)
    n1 = int(binary.sum())
    n2 = len(binary) - n1
    if n1 == 0 or n2 == 0:
        return 0.0, 1.0
    runs = 1 + int((binary[1:] != binary[:-1]).sum())
    mean = 2 * n1 * n2 / (n1 + n2) + 1
    var = 2 * n1 * n2 * (2 * n1 * n2 - n1 - n2) / ((n1 + n2) ** 2 * (n1 + n2 - 1))
    z = (runs - mean) / np.sqrt(var)
    return float(z), float(2 * stats.norm.sf(abs(z)))


def serial_phi_test(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """每个号码的一阶自相关（φ 系数）及其 p 值。"""
    prev = matrix[:-1].astype(bool)
    curr = matrix[1:].astype(bool)
    phis = np.empty(matrix.shape[1])
    pvals = np.empty(matrix.shape[1])
    for j in range(matrix.shape[1]):
        table = pd.crosstab(prev[:, j], curr[:, j]).to_numpy()
        if table.shape != (2, 2):
            phis[j] = 0.0
            pvals[j] = 1.0
            continue
        chi2, p, _, _ = stats.chi2_contingency(table, correction=False)
        phis[j] = np.sqrt(chi2 / table.sum()) * np.sign(table[0, 0] * table[1, 1] - table[0, 1] * table[1, 0])
        pvals[j] = p
    return phis, pvals


def gap_test(matrix: np.ndarray, rate: float) -> tuple[np.ndarray, np.ndarray]:
    """每个号码的遗漏间隔分布 vs 几何分布（分箱卡方）。"""
    n, pool = matrix.shape
    ps = np.empty(pool)
    max_gap = 25 if rate < 0.15 else 40
    bins = np.arange(0, max_gap + 1)
    # scipy 的 geom 支持 k=1,2,...：P(X=k)=(1-p)^(k-1)p，这里 X 是"间隔期数+1"
    geom = stats.geom.pmf(bins + 1, rate)
    geom[-1] = 1 - geom[:-1].sum()  # 最后一箱为 >= max_gap
    for j in range(pool):
        idx = np.flatnonzero(matrix[:, j])
        if len(idx) < 10:
            ps[j] = 1.0
            continue
        gaps = np.diff(idx) - 1
        obs = np.bincount(np.minimum(gaps, max_gap), minlength=max_gap + 1).astype(float)
        _, _, p, _ = chi2_binned(obs, geom)
        ps[j] = p
    return ps, geom


def pair_permutation_test(matrix: np.ndarray, n_sims: int = N_PERMUTATIONS, seed: int = 20261104):
    """号码对共现的蒙特卡洛检验。

    每次模拟生成与真实数据同样期数的均匀随机开奖，计算号码对频数的 χ² 统计量，
    用经验分布得到 p 值。这样绕开了"组合计数之间不独立"导致的解析分布错误。
    """
    n, pool = matrix.shape
    k = int(matrix.sum(axis=1)[0])
    iu = np.triu_indices(pool, 1)
    expected_pair = n * comb(pool - 2, k - 2) / comb(pool, k)

    def statistic(pair_counts: np.ndarray) -> float:
        return float(((pair_counts - expected_pair) ** 2 / expected_pair).sum())

    observed = matrix.T.astype(np.float64) @ matrix.astype(np.float64)
    obs_stat = statistic(observed[iu])

    rng = np.random.default_rng(seed)
    sims = np.empty(n_sims)
    for s in range(n_sims):
        ranks = rng.random((n, pool))
        idx = np.argpartition(ranks, k - 1, axis=1)[:, :k]
        x = np.zeros((n, pool), dtype=np.float32)
        np.put_along_axis(x, idx, 1.0, axis=1)
        counts = x.T @ x
        sims[s] = statistic(counts[iu])
    pvalue = (1 + int((sims >= obs_stat).sum())) / (n_sims + 1)
    z = (observed - expected_pair) / np.sqrt(expected_pair * (1 - k * (k - 1) / (pool * (pool - 1))))
    return obs_stat, pvalue, z, sims


def feature_tests(data: LotteryData, features: pd.DataFrame) -> list[TestResult]:
    game = data.game
    table = feature_table(game)
    results: list[TestResult] = []
    specs = [
        ("sum", "和值"),
        ("span", "跨度"),
        ("odd", "奇数个数"),
        ("big", "大号个数"),
        ("consecutive", "连号组数"),
        ("ac", "AC 值"),
        ("zone_pattern", "三区比"),
        ("tail_distinct", "不同尾数个数"),
    ]
    for key, label in specs:
        observed_series = features[key].astype(str)
        support = list(table.counts[key].keys())
        obs = observed_series.value_counts().reindex(support, fill_value=0).to_numpy(dtype=float)
        exp_prob = np.array([table.counts[key][s] / table.total for s in support])
        # 真实数据中可能出现的、枚举里没有的类别（理论上不会）
        extra = observed_series[~observed_series.isin(support)].value_counts()
        if len(extra):
            obs = np.concatenate([obs, extra.to_numpy(dtype=float)])
            exp_prob = np.concatenate([exp_prob, np.zeros(len(extra))])
        stat, dof, p, nbins = chi2_binned(obs, exp_prob)
        results.append(
            TestResult(
                game=game.key,
                category="形态分布",
                name=f"{label} vs 精确分布 χ²",
                statistic=stat,
                dof=dof,
                pvalue=p,
                note=f"{nbins} 个合并类别",
            )
        )
    return results


def analyze_game(data: LotteryData) -> dict:
    game: Game = data.game
    features = draw_features(data)
    results: list[TestResult] = []

    # 1) 边际均匀性
    for label, matrix in (("前区" if game.key == "dlt" else "红球", data.front), ("后区" if game.key == "dlt" else "蓝球", data.back)):
        result, counts, residuals = number_uniformity(matrix, label, game.key)
        results.append(result)
        if label in ("红球", "前区"):
            front_counts, front_residuals = counts, residuals
        else:
            back_counts, back_residuals = counts, residuals

    # 2) 每个号码的二项检验（双侧），用于逐号 FDR
    per_number_p = np.array(
        [stats.binomtest(int(c), data.n, game.front_rate).pvalue for c in front_counts]
    )

    # 3) 形态分布
    results.extend(feature_tests(data, features))

    # 4) 一阶序列相关
    phis, phi_p = serial_phi_test(data.front)
    results.append(
        TestResult(
            game=game.key,
            category="序列相关",
            name="号码一阶自相关（似然比 χ² 汇总）",
            statistic=float(-2 * np.log(np.clip(phi_p, 1e-300, 1)).sum()),
            dof=2 * game.front_pool,
            pvalue=float(stats.chi2.sf(-2 * np.log(np.clip(phi_p, 1e-300, 1)).sum(), 2 * game.front_pool)),
            note="Fisher 合并；各号码 2×2 独立性检验",
        )
    )

    # 5) 遗漏间隔 vs 几何分布
    gap_p, geom_pmf = gap_test(data.front, game.front_rate)
    results.append(
        TestResult(
            game=game.key,
            category="遗漏",
            name="遗漏间隔几何分布拟合（Fisher 合并）",
            statistic=float(-2 * np.log(np.clip(gap_p, 1e-300, 1)).sum()),
            dof=2 * game.front_pool,
            pvalue=float(stats.chi2.sf(-2 * np.log(np.clip(gap_p, 1e-300, 1)).sum(), 2 * game.front_pool)),
            note="每个号码的间隔分布单独做 χ² 后合并",
        )
    )

    # 6) 和值 / 后区的独立性
    back_feature = "back" if "back" in features.columns else "back_sum"
    stat, p, dof, _ = stats.chi2_contingency(
        pd.crosstab(pd.qcut(features["sum"], 6, duplicates="drop"), features[back_feature])
    )
    results.append(
        TestResult(game=game.key, category="独立性", name="前区和值 × 后区号码 列联表 χ²", statistic=float(stat), dof=float(dof), pvalue=float(p))
    )

    # 7) 相邻两期重号 vs 超几何分布
    repeat = features["repeat"].dropna().astype(int)
    max_repeat = min(game.front_pick, game.front_pick)
    obs = np.bincount(repeat, minlength=max_repeat + 1)[: max_repeat + 1].astype(float)
    exp = hypergeom_pmf(game.front_pool, game.front_pick, game.front_pick)[: max_repeat + 1]
    stat, dof, p, _ = chi2_binned(obs, exp)
    results.append(
        TestResult(game=game.key, category="独立性", name="相邻两期重号数 vs 超几何", statistic=stat, dof=dof, pvalue=p)
    )

    # 8) 和值序列的随机性：游程 + Ljung–Box + 趋势
    z, p_runs = runs_test(features["sum"])
    results.append(TestResult(game=game.key, category="序列相关", name="和值游程检验", statistic=z, dof=None, pvalue=p_runs))
    q, lags, p_lb = ljung_box(features["sum"], 12)
    results.append(TestResult(game=game.key, category="序列相关", name="和值 Ljung–Box(12)", statistic=q, dof=lags, pvalue=p_lb))
    tau, p_trend = stats.kendalltau(np.arange(len(features)), features["sum"])
    results.append(TestResult(game=game.key, category="序列相关", name="和值 Kendall 趋势检验", statistic=float(tau), dof=None, pvalue=float(p_trend)))

    # 9) 号码对共现（蒙特卡洛）
    pair_stat, pair_p, pair_z, pair_sims = pair_permutation_test(data.front)
    results.append(
        TestResult(
            game=game.key,
            category="独立性",
            name="号码对共现 χ²（蒙特卡洛）",
            statistic=pair_stat,
            dof=None,
            pvalue=pair_p,
            note=f"{N_PERMUTATIONS} 次置换",
        )
    )

    frame = pd.DataFrame([r.as_row() for r in results])
    frame["q_value"] = fdr_bh(frame["p_value"].to_numpy())
    frame["significant_fdr"] = frame["q_value"] < 0.05

    # 号码频率的信息熵
    freq = front_counts / front_counts.sum()
    entropy = float(-(freq * np.log2(freq)).sum())
    max_entropy = float(np.log2(game.front_pool))

    return {
        "game": game.key,
        "features": features,
        "results": frame,
        "front_counts": front_counts,
        "back_counts": back_counts,
        "front_residuals": front_residuals,
        "back_residuals": back_residuals,
        "per_number_q": fdr_bh(per_number_p),
        "phi": phis,
        "phi_q": fdr_bh(phi_p),
        "gap_q": fdr_bh(gap_p),
        "pair_z": pair_z,
        "pair_sims": pair_sims,
        "pair_stat": pair_stat,
        "pair_p": pair_p,
        "entropy": entropy,
        "max_entropy": max_entropy,
        "current_omission": current_omission(data.front),
    }
