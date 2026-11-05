"""号码"流行度"与奖金分摊。

一个反直觉但重要的事实：选号不能改变中奖概率，却能改变**中奖后能分到多少钱**。
双色球/大乐透的一、二等奖是浮动奖（奖池按中奖注数均分），
如果某组号码被大量彩民选中，开出来后中奖注数就多，单注奖金就被摊薄。

本模块用"一等奖中出注数"作为组合流行度的代理变量，在控制销售额、奖池规模与时间趋势后，
逐个检验号码形态是否影响中奖人数。每个形态单独建模，避免强共线性把系数符号带反。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .config import Game
from .data import LotteryData

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
    """普通最小二乘 + HC1 异方差稳健标准误。"""
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
    """逐个形态做回归：y ~ 1 + log(销量) + log(奖池) + 时间 + 形态。"""
    frame = _raw_features(data, features)
    y = np.log1p(data.df["p1_count"].fillna(0).astype(float).to_numpy())
    controls = ["log_sales", "log_pool", "time"]

    rows = []
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
    # 对 8 个形态检验做 BH 校正
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
    """按和值分位分箱，展示每百万销量对应的一等奖中出注数。"""
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
