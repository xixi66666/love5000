"""统计检验层。

核心原则：
* 每个检验都对应一个可证伪的零假设（通常是"开奖等价于均匀随机抽样"）；
* 形态类检验使用**精确组合分布**作为期望，而不是正态近似；
* 大量检验必然产生假阳性，因此统一做 Benjamini–Hochberg FDR 校正；
* 对号码对共现这类统计量分布未知的检验，用蒙特卡洛置换检验。

输出统一为 TestResult 列表，便于汇总成表和图。

公开面：:class:`TestResult`（单个检验的结论）、:func:`fdr_bh` 与各检验函数
（:func:`number_uniformity` / :func:`feature_tests` / :func:`serial_phi_test` /
:func:`gap_test` / :func:`pair_permutation_test` / :func:`runs_test` /
:func:`ljung_box` / :func:`chi2_binned`），总入口是 :func:`analyze_game`。

口径：除特别说明外，p 值都是双侧、取值 0–1；统计量无量纲；``q_value`` 是 BH 校正后的
错误发现率。检验的追加顺序被 :mod:`lottery.report` 按固定行号引用，见 :func:`analyze_game`。

边界：不拒绝零假设只说明“这份样本看不出偏离”，不等于证明了开奖可预测；任何“显著”
结果都要先排除多重比较、数据断点与样本构造问题，更不能据此下注。
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

# 置换次数：300 次只能把 p 值分辨到约 0.003，足以发现“强规律”，但检测不到极弱偏差。
N_PERMUTATIONS = 300


@dataclass
class TestResult:
    """一个统计检验的结论。

    Attributes:
        game: 彩种 key。
        category: 检验类别（边际均匀性 / 形态分布 / 序列相关 / 独立性 / 遗漏）。
        name: 检验名称，会直接显示在报告表格里。
        statistic: 检验统计量（卡方、z 或 τ，无量纲）；部分检验没有，置 ``None``。
        dof: 自由度；非卡方类检验为 ``None``。
        pvalue: 原始 p 值（0–1，双侧）。
        note: 补充说明，例如合并箱数或置换次数；空串表示无。
    """

    game: str
    category: str
    name: str
    statistic: float | None
    dof: float | None
    pvalue: float
    note: str = ""

    def as_row(self) -> dict:
        """转成一行表数据。

        键名与报告表格列一致：``name`` 改名为 ``test``、``pvalue`` 改名为 ``p_value``，
        其余原样；``statistic`` / ``dof`` 可能是 ``None``，由渲染层显示成 ``—``。
        """
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
    """Benjamini–Hochberg 校正后的 q 值。

    Args:
        pvalues: 原始 p 值数组。

    Returns:
        与输入同序的 q 值数组，已截断到 [0, 1]。

    实现要点：先排序算出 ``p·m/rank``，再从大到小取累计最小做单调化，保证 q 不会
    随 p 增大而减小；一次调用只用一个 ``m``，因此调用方应把“同一批假设”一次性传入。
    """
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

    合并规则：按期望频数从小到大累加，累计期望达到 5 就切一箱，最后剩余的尾部并入
    最后一箱。这样满足卡方检验“每箱期望 ≥5”的经验要求，又不会人为丢掉稀有类别；
    自由度取“合并后箱数 − 1”且至少为 1，避免只剩一箱时出现 df=0。
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
    """单侧（前区或后区）号码出现频数的均匀性卡方检验。

    零假设：每个号码在任意一期被摇出的概率都相同。

    Args:
        matrix: ``(n, pool)`` 的 0/1 指示矩阵。
        label: 用于文案的区域名（“红球”“蓝球”“前区”“后区”）。
        game: 彩种 key，写进 :class:`TestResult`。

    Returns:
        ``(结果, 各号码出现次数, 标准化残差)``。残差为 ``(O − E)/√(E(1−p))``，
        用来判断“哪个号码偏得最多”；自由度是 ``pool − 1``。
    """
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
    """把 p 值排序后与 Uniform(0,1) 分位数对照。

    Returns:
        ``(理论分位数, 排序后的 p 值)``。期望分位数取 ``(i − 0.5)/m``，
        避免端点取到 0 或 1 把散点图拉偏。
    """
    p = np.sort(np.asarray(pvalues, dtype=float))
    m = len(p)
    expected = (np.arange(1, m + 1) - 0.5) / m
    return expected, p


def ljung_box(series: np.ndarray, lags: int = 12) -> tuple[float, int, float]:
    """Ljung–Box 白噪声检验：检验前 lags 阶自相关是否同时为 0。

    Args:
        series: 一维序列（例如每期和值）。
        lags: 滞后阶数，默认 12。

    Returns:
        ``(Q 统计量, 自由度 = lags, p 值)``；Q 近似服从卡方分布。p 值小说明序列存在
        可被线性模型利用的自相关。
    """
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
    """Wald–Wolfowitz 游程检验（以中位数为界）。

    把序列按“大于中位数 / 不大于中位数”转成 0/1，数出连续段（游程）个数，
    再与随机序列的期望游程数比较：游程过少说明有聚集趋势，过多说明有交替倾向。

    Returns:
        ``(z, p)``。若所有值都在中位数同一侧（``n1`` 或 ``n2`` 为 0），检验退化，
        直接返回 ``(0.0, 1.0)`` 而不是产生除零或非法方差。
    """
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
    """每个号码的一阶自相关（φ 系数）及其 p 值。

    对每个号码构造“上期是否出现 × 本期是否出现”的 2×2 列联表做独立性卡方，
    ``φ = √(χ²/n)`` 再乘上相关方向的符号。

    Returns:
        ``(phis, pvals)``，长度等于号码池大小。某个号码在样本里恒定出现或恒定不出时
        列联表不是 2×2，此时记 ``φ=0, p=1``（无法判定）。
    """
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
    """每个号码的遗漏间隔分布 vs 几何分布（分箱卡方）。

    Args:
        matrix: ``(n, pool)`` 的 0/1 指示矩阵。
        rate: 单个号码每期出现的边际概率，即几何分布的参数 p。

    Returns:
        ``(每个号码的 p 值, 理论几何分布 pmf)``。间隔的最大箱按出现率取 25 或 40，
        最后一箱是“≥ max_gap”的合并尾；出现次数少于 10 的号码样本不足，直接记 p=1。
    """
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

    Args:
        matrix: ``(n, pool)`` 的 0/1 指示矩阵。
        n_sims: 置换次数，默认 :data:`N_PERMUTATIONS`。
        seed: 随机种子，固定后结果可复现。

    Returns:
        ``(观测统计量, p 值, z 矩阵, 模拟统计量数组)``。p 值取
        ``(1 + #{模拟 ≥ 观测}) / (n_sims + 1)``，避免出现 p=0；z 矩阵是两两共现频数的
        标准化残差，图形上用来找偏离最大的号码对。

    实现要点：模拟用 ``argpartition`` 每期取分数最高的 k 个号，等价于不放回均匀抽样，
    比逐期调用 ``choice`` 快一个量级。
    """
    n, pool = matrix.shape
    k = int(matrix.sum(axis=1)[0])
    iu = np.triu_indices(pool, 1)
    expected_pair = n * comb(pool - 2, k - 2) / comb(pool, k)

    def statistic(pair_counts: np.ndarray) -> float:
        """号码对共现频数的 χ² 统计量（期望值由组合数解析给出）。"""
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
    """把逐期形态分布与精确组合分布逐一做卡方拟合优度检验。

    覆盖 8 个形态：和值、跨度、奇数个数、大号个数、连号组数、AC 值、三区比、不同尾数个数。

    Args:
        data: 开奖数据（只用 ``game``）。
        features: :func:`lottery.features.draw_features` 的结果。

    Returns:
        8 个 :class:`TestResult`，``category`` 统一为“形态分布”，``note`` 记录合并后的箱数。

    兜底：若实测出现枚举里没有的类别（理论上不会，例如数据被手工改过），会给它补一个
    期望概率为 0 的额外箱，由 :func:`chi2_binned` 并进相邻箱，而不是直接抛错。
    """
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
    """跑完一个彩种的全部统计检验，并把图表要用的中间量一并返回。

    Args:
        data: 已加载并校验的开奖数据。

    Returns:
        dict，键与含义：
            * ``game`` / ``features``：彩种 key 与逐期特征表；
            * ``results``：检验汇总表（每行一个 :class:`TestResult`，另有
              ``q_value`` / ``significant_fdr`` 两列）；
            * ``front_counts`` / ``back_counts`` / ``front_residuals`` /
              ``back_residuals``：频数与标准化残差；
            * ``per_number_q`` / ``phi_q`` / ``gap_q``：逐号码多重比较的 q 值；
            * ``pair_z`` / ``pair_sims`` / ``pair_stat`` / ``pair_p``：号码对共现检验；
            * ``entropy`` / ``max_entropy``：号码频率的信息熵与上限（bit）；
            * ``current_omission``：最新一期之后的遗漏（期）。

    位置约定：``results`` 的行序就是本函数追加检验的顺序，:mod:`lottery.report` 用固定
    ``iloc`` 位置取用其中的 ``0``（前区频数）、``1``（后区频数）、``10``（一阶自相关）、
    ``14``（和值游程）、``15``（和值 Ljung–Box）；新增检验不要插在这些位置之前。
    """
    game: Game = data.game
    features = draw_features(data)
    results: list[TestResult] = []

    # 1) 边际均匀性：零假设是每个号码每期出现的概率相同。
    for label, matrix in (("前区" if game.key == "dlt" else "红球", data.front), ("后区" if game.key == "dlt" else "蓝球", data.back)):
        result, counts, residuals = number_uniformity(matrix, label, game.key)
        results.append(result)
        if label in ("红球", "前区"):
            front_counts, front_residuals = counts, residuals
        else:
            back_counts, back_residuals = counts, residuals

    # 2) 每个号码的二项检验（双侧）：单号是否偏多/偏少；33 或 35 次比较统一做 FDR。
    per_number_p = np.array(
        [stats.binomtest(int(c), data.n, game.front_rate).pvalue for c in front_counts]
    )

    # 3) 形态分布：和值、跨度、奇偶等对照精确组合分布，而不是正态近似。
    results.extend(feature_tests(data, features))

    # 4) 一阶序列相关：把每个号码的 2×2 独立性检验用 Fisher 方法合并成一个总体检验。
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

    # 5) 遗漏间隔 vs 几何分布：独立开奖下遗漏长度必然服从几何分布。
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

    # 6) 和值 / 后区的独立性：前后区若有联动，列联表卡方会显著。
    back_feature = "back" if "back" in features.columns else "back_sum"
    stat, p, dof, _ = stats.chi2_contingency(
        pd.crosstab(pd.qcut(features["sum"], 6, duplicates="drop"), features[back_feature])
    )
    results.append(
        TestResult(game=game.key, category="独立性", name="前区和值 × 后区号码 列联表 χ²", statistic=float(stat), dof=float(dof), pvalue=float(p))
    )

    # 7) 相邻两期重号 vs 超几何分布：检验“上一期号码是否更可能再次出现”。
    repeat = features["repeat"].dropna().astype(int)
    # 重号个数的理论上限就是前区选号个数，不可能更多。
    max_repeat = min(game.front_pick, game.front_pick)
    obs = np.bincount(repeat, minlength=max_repeat + 1)[: max_repeat + 1].astype(float)
    exp = hypergeom_pmf(game.front_pool, game.front_pick, game.front_pick)[: max_repeat + 1]
    stat, dof, p, _ = chi2_binned(obs, exp)
    results.append(
        TestResult(game=game.key, category="独立性", name="相邻两期重号数 vs 超几何", statistic=stat, dof=dof, pvalue=p)
    )

    # 8) 和值序列的随机性：游程（聚集）、Ljung–Box（自相关）、Kendall τ（单调趋势）三个角度。
    z, p_runs = runs_test(features["sum"])
    results.append(TestResult(game=game.key, category="序列相关", name="和值游程检验", statistic=z, dof=None, pvalue=p_runs))
    q, lags, p_lb = ljung_box(features["sum"], 12)
    results.append(TestResult(game=game.key, category="序列相关", name="和值 Ljung–Box(12)", statistic=q, dof=lags, pvalue=p_lb))
    tau, p_trend = stats.kendalltau(np.arange(len(features)), features["sum"])
    results.append(TestResult(game=game.key, category="序列相关", name="和值 Kendall 趋势检验", statistic=float(tau), dof=None, pvalue=float(p_trend)))

    # 9) 号码对共现（蒙特卡洛）：解析分布不可用，用同一期数下的均匀随机重抽做经验 p 值。
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
    # 全部检验统一做 BH 校正；报告只把 q<0.05 视为“不通过”，未校正的 p 值仅作参考。
    frame["q_value"] = fdr_bh(frame["p_value"].to_numpy())
    frame["significant_fdr"] = frame["q_value"] < 0.05

    # 号码频率的信息熵（bit）：均匀分布时达到 log2(pool) 的上限，越接近上限越均匀。
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
