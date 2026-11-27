"""号码"流行度"与奖金分摊。

一个反直觉但重要的事实：选号不能改变中奖概率，却能改变**中奖后能分到多少钱**。
双色球/大乐透的一、二等奖是浮动奖（奖池按中奖注数均分），
如果某组号码被大量彩民选中，开出来后中奖注数就多，单注奖金就被摊薄。

本模块用"一等奖中出注数"作为组合流行度的代理变量，在控制销售额、奖池规模与时间趋势后，
逐个检验号码形态是否影响中奖人数。每个形态单独建模，避免强共线性把系数符号带反。

公开面：:func:`popularity_regression`（逐形态回归表）、:func:`popularity_bins`（和值分箱）、
:func:`ols_hc1`（带 HC1 稳健标准误的 OLS）。

口径与单位：
    * 因变量是 ``log1p(一等奖注数)``，系数读作“对数注数的变化”，
      ``effect_pct = (e^β − 1) × 100`` 换算成百分比；
    * 形态变量在回归前标准化，β 表示“每变动一个标准差”的约当变化；
    * 控制变量为 ``log(销量)``、``log(奖池)`` 与时间趋势，缓解“卖得多所以中得多”的混淆；
    * 8 个形态检验统一做 Benjamini–Hochberg 校正，只有 q<0.05 才视为显著。

边界：流行度只是“一等奖中出注数”这个代理变量，无法区分“号码被买得多”与“开奖号码
本身更常见”。即使系数显著，它描述的也只是选号偏好造成的奖金分摊差异，
不改变任何一注的中奖概率，更不构成购彩建议。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .config import Game
from .data import LotteryData

# 逐个检验的形态清单（变量名, 中文标签）；顺序决定表格与图 16 的排列。
# 每个形态单独建模，避免强共线性把系数符号带反。
FEATURES = [
    ("sum", "和值"),
    ("n_le12", "≤12 的个数（生日号）"),
    ("n_le31", "≤31 的个数"),
    ("lucky", "幸运数字个数"),
    ("consecutive", "连号组数"),
    ("tail_same", "同尾 ≥3 个"),
    ("all_odd", "全奇数"),
    ("all_even", "全偶数"),
]


def _raw_features(data: LotteryData, features: pd.DataFrame) -> pd.DataFrame:
    """构造回归用的原始变量表（尚未标准化）。

    Args:
        data: 开奖数据，需含 ``sales`` / ``pool`` 列（元）。
        features: 逐期特征表，提供 ``sum`` / ``consecutive`` / ``odd``。

    Returns:
        DataFrame，含 ``log_sales`` / ``log_pool``（对元取自然对数，先 clip 到 ≥1
        以避免 log(0)）、``time``（0–1 的期次比例，用于吸收长期趋势）、``sum``、
        ``n_le12`` / ``n_le31``（号码中 ≤12 / ≤31 的个数，对应“生日号”）、
        ``lucky``（民间幸运数字 6/8/9/16/18/28 的个数）、``consecutive``（连号对数）、
        ``tail_same``（同尾 ≥3 个的二值标记）、``all_odd`` / ``all_even``（全奇 / 全偶标记）。
    """
    game: Game = data.game
    numbers = np.array([np.flatnonzero(row) + 1 for row in data.front])
    tails = numbers % 10
    tail_same = np.array([np.bincount(row, minlength=10).max() >= 3 for row in tails]).astype(float)
    return pd.DataFrame(
        {
            "log_sales": np.log(data.df["sales"].clip(lower=1).astype(float)),
            "log_pool": np.log(data.df["pool"].clip(lower=1).astype(float)),
            "time": np.arange(len(data.df)) / len(data.df),
            "sum": features["sum"].to_numpy(dtype=float),
            "n_le12": (numbers <= 12).sum(axis=1).astype(float),
            "n_le31": (numbers <= 31).sum(axis=1).astype(float),
            "lucky": np.isin(numbers, (6, 8, 9, 16, 18, 28)).sum(axis=1).astype(float),
            "consecutive": features["consecutive"].to_numpy(dtype=float),
            "tail_same": tail_same,
            "all_odd": (features["odd"].to_numpy() == game.front_pick).astype(float),
            "all_even": (features["odd"].to_numpy() == 0).astype(float),
        }
    )


def ols_hc1(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """普通最小二乘 + HC1 异方差稳健标准误。

    Args:
        x: ``(n, k)`` 设计矩阵，首列由调用方显式拼上常数项。
        y: ``(n,)`` 因变量。

    Returns:
        ``(beta, se, r2)``：系数、HC1 稳健标准误与决定系数；``se`` 用于构造 z 统计量。

    实现要点：用 :func:`numpy.linalg.pinv` 而不是求逆，设计矩阵近奇异时仍能给出解；
    HC1 的 ``n/(n-k)`` 是自由度修正，样本量远大于变量数时影响可忽略。
    真正的风险是 ``n <= k``：修正因子会除以 0，标准误退化为 ``inf`` 或 ``nan``。
    """
    xtx_inv = np.linalg.pinv(x.T @ x)
    beta = xtx_inv @ x.T @ y
    resid = y - x @ beta
    n, k = x.shape
    meat = (x * (resid**2)[:, None]).T @ x
    cov = xtx_inv @ meat @ xtx_inv * n / (n - k)
    se = np.sqrt(np.diag(cov))
    ss_res = float(resid @ resid)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    return beta, se, 1 - ss_res / ss_tot


def popularity_regression(data: LotteryData, features: pd.DataFrame) -> pd.DataFrame:
    """逐个形态做回归：y ~ 1 + log(销量) + log(奖池) + 时间 + 形态。

    Args:
        data: 开奖数据（需 ``p1_count`` / ``sales`` / ``pool`` 列）。
        features: 逐期特征表。

    Returns:
        DataFrame，每行一个形态，列为 ``variable``（变量名）/ ``label``（中文标签）/
        ``coef``（标准化系数）/ ``se``（HC1 稳健标准误）/ ``z`` / ``p_value``（双侧正态
        p 值）/ ``effect_pct``（约当百分比变化）/ ``r2`` / ``n`` / ``q_value``
        （8 次检验的 BH 校正结果）。
    """
    frame = _raw_features(data, features)
    y = np.log1p(data.df["p1_count"].fillna(0).astype(float).to_numpy())
    controls = ["log_sales", "log_pool", "time"]

    rows = []
    # 每个形态共享同一组控制变量，但形态之间不互相进入，避免共线性让系数反号。
    for name, label in FEATURES:
        feature = frame[name].to_numpy(dtype=float)
        std = feature.std(ddof=0)
        feature_std = (feature - feature.mean()) / (std if std else 1)
        x = np.column_stack(
            [np.ones(len(frame))]
            + [((frame[c] - frame[c].mean()) / (frame[c].std(ddof=0) or 1)).to_numpy() for c in controls]
            + [feature_std]
        )
        beta, se, r2 = ols_hc1(x, y)
        coef, coef_se = beta[-1], se[-1]
        z = coef / coef_se
        rows.append(
            {
                "variable": name,
                "label": label,
                "coef": coef,
                "se": coef_se,
                "z": z,
                "p_value": float(2 * stats.norm.sf(abs(z))),
                "effect_pct": float((np.exp(coef) - 1) * 100),
                "r2": r2,
                "n": len(y),
            }
        )

    table = pd.DataFrame(rows)
    # 对 8 个形态检验做 BH 校正：从大到小取累计最小做单调化，保证 q 不随 p 增大而减小。
    order = np.argsort(table["p_value"].to_numpy())
    m = len(table)
    q = np.empty(m)
    ranked = table["p_value"].to_numpy()[order]
    q_sorted = ranked * m / np.arange(1, m + 1)
    q_sorted = np.minimum.accumulate(q_sorted[::-1])[::-1]
    q[order] = np.clip(q_sorted, 0, 1)
    table["q_value"] = q
    return table


def popularity_bins(data: LotteryData, features: pd.DataFrame, quantiles: int = 8) -> pd.DataFrame:
    """按和值分位分箱，展示每百万销量对应的一等奖中出注数。

    Args:
        data: 开奖数据。
        features: 逐期特征表（提供 ``sum``）。
        quantiles: 目标分箱数；和值重复值多时实际箱数会更少（``duplicates="drop"``）。

    Returns:
        DataFrame，列为 ``bin``（分位区间）/ ``sum_mean``（箱内平均和值）/
        ``winners``（箱内平均一等奖注数）/ ``winners_per_million``（每百万元销量对应的
        一等奖注数，取中位数）/ ``draws``（箱内期数）。
    """
    df = data.df.copy()
    df["sum"] = features["sum"].to_numpy()
    df["p1_count"] = df["p1_count"].fillna(0)
    df["sales_m"] = df["sales"] / 1e6
    df["winners_per_million"] = df["p1_count"] / df["sales_m"].replace(0, np.nan)
    df["bin"] = pd.qcut(df["sum"], quantiles, duplicates="drop")
    out = (
        df.groupby("bin", observed=True)
        .agg(
            sum_mean=("sum", "mean"),
            winners=("p1_count", "mean"),
            winners_per_million=("winners_per_million", "median"),
            draws=("p1_count", "size"),
        )
        .reset_index()
    )
    out["sum_mean"] = out["sum_mean"].astype(float)
    return out
