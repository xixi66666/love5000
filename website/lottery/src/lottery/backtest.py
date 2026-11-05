"""严格回测：只用历史信息选号，逐期结算真实奖级与奖金。

评价分两层：
* 结果层：命中个数、奖级分布、投入产出比（与理论超几何/期望值对比）；
* 概率层：对数损失、Brier 分数、校准曲线——比"中没中"灵敏得多，
  因为对数损失会惩罚过度自信的错误概率。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .combinatorics import hypergeom_pmf, tier_probabilities
from .config import PRIZE_TIER, Game
from .data import LotteryData, prize_amounts
from .models import Context, Strategy, build_context


@dataclass
class BacktestResult:
    game: str
    start: int
    end: int
    ledger: pd.DataFrame
    summary: pd.DataFrame
    hit_distribution: pd.DataFrame
    calibration: pd.DataFrame
    logloss: pd.DataFrame


def run_backtest(
    data: LotteryData,
    features: pd.DataFrame,
    strategies: list[Strategy],
    start: int,
    end: int | None = None,
    seed: int = 20261104,
) -> BacktestResult:
    game: Game = data.game
    end = data.n if end is None else min(end, data.n)
    ctx = build_context(data, features)
    amounts = prize_amounts(game.key)
    issues = data.df["issue"].to_numpy()
    tier_fn = PRIZE_TIER[game.key]
    rng = np.random.default_rng(seed)

    actual_front = [set(np.flatnonzero(row) + 1) for row in data.front]
    actual_back = [set(np.flatnonzero(row) + 1) for row in data.back]

    ledger: list[dict] = []
    for t in range(start, end):
        for strategy in strategies:
            front = strategy.pick_front(ctx, t, rng)
            back = strategy.pick_back(ctx, t, rng)
            front_hits = len(actual_front[t] & set(front.tolist()))
            back_hits = len(actual_back[t] & set(back.tolist()))
            tier = tier_fn(front_hits, back_hits)
            issue = issues[t]
            payout = float(amounts.loc[issue, tier]) if tier else 0.0
            ledger.append(
                {
                    "t": t,
                    "issue": issue,
                    "date": data.df["date"].iloc[t],
                    "strategy": strategy.name,
                    "front_hits": front_hits,
                    "back_hits": back_hits,
                    "tier": tier,
                    "payout": payout,
                    "cost": game.price,
                    "front": " ".join(f"{n:02d}" for n in front),
                    "back": " ".join(f"{n:02d}" for n in back),
                }
            )

    ledger_df = pd.DataFrame(ledger)

    # ---- 汇总 ----------------------------------------------------------
    theoretical_hits = game.front_mean_hits
    rows = []
    for name, group in ledger_df.groupby("strategy", sort=False):
        hits = group["front_hits"].to_numpy(dtype=float)
        n = len(hits)
        mean = hits.mean()
        se = hits.std(ddof=1) / np.sqrt(n) if n > 1 else np.nan
        cost = group["cost"].sum()
        payout = group["payout"].sum()
        rows.append(
            {
                "strategy": name,
                "draws": n,
                "mean_front_hits": mean,
                "theoretical_hits": theoretical_hits,
                "diff": mean - theoretical_hits,
                "se": se,
                "t_stat": (mean - theoretical_hits) / se if se else np.nan,
                "any_prize_rate": float((group["tier"] > 0).mean()),
                "theoretical_any_prize": float(tier_probabilities(game)[1:].sum()),
                "jackpots": int((group["tier"] == 1).sum()),
                "cost": cost,
                "payout": payout,
                "roi": payout / cost - 1 if cost else np.nan,
            }
        )
    summary = pd.DataFrame(rows).sort_values("mean_front_hits", ascending=False)

    # ---- 命中数分布 vs 超几何 -------------------------------------------
    k = game.front_pick
    theory = hypergeom_pmf(game.front_pool, k, k)
    dist_rows = []
    for name, group in ledger_df.groupby("strategy", sort=False):
        counts = np.bincount(group["front_hits"], minlength=k + 1) / len(group)
        dist_rows.append({"strategy": name, "hits": np.arange(k + 1), "observed": counts, "theory": theory[: k + 1]})
    hit_distribution = pd.concat(
        [pd.DataFrame({"strategy": r["strategy"], "hits": r["hits"], "observed": r["observed"], "theory": r["theory"]}) for r in dist_rows],
        ignore_index=True,
    )

    # ---- 概率层评价 ------------------------------------------------------
    logloss_rows = []
    calib_points = []
    uniform_ll = -np.log(1.0 / game.front_pool) * k
    for strategy in strategies:
        probs = strategy.probabilities(ctx, 0, "front")
        if probs is None:
            continue
        ll_values = []
        preds, outcomes = [], []
        for t in range(start, end):
            p = strategy.probabilities(ctx, t, "front")
            p = np.asarray(p, dtype=float)
            p = np.clip(p / p.sum(), 1e-12, 1)
            y = data.front[t].astype(bool)
            ll_values.append(-np.log(p[y]).sum())
            preds.append(p)
            outcomes.append(y)
        ll = np.array(ll_values)
        preds_arr = np.concatenate(preds)
        outcomes_arr = np.concatenate(outcomes).astype(float)
        brier = float(np.mean((outcomes_arr - preds_arr) ** 2))
        logloss_rows.append(
            {
                "strategy": strategy.name,
                "mean_logloss": float(ll.mean()),
                "uniform_logloss": uniform_ll,
                "lift": uniform_ll - float(ll.mean()),
                "brier": brier,
                "uniform_brier": float(game.front_rate * (1 - game.front_rate)),
                "per_draw": ll,
            }
        )
        # 校准：把预测概率分箱，比较预测均值与实测频率
        bins = np.quantile(preds_arr, np.linspace(0, 1, 11))
        bins = np.unique(bins)
        idx = np.clip(np.digitize(preds_arr, bins[1:-1]), 0, len(bins) - 2)
        for b in range(len(bins) - 1):
            mask = idx == b
            if mask.sum() < 30:
                continue
            calib_points.append(
                {
                    "strategy": strategy.name,
                    "bin": b,
                    "predicted": float(preds_arr[mask].mean()),
                    "observed": float(outcomes_arr[mask].mean()),
                    "count": int(mask.sum()),
                }
            )
    logloss = pd.DataFrame(logloss_rows)
    calibration = pd.DataFrame(calib_points)

    return BacktestResult(
        game=game.key,
        start=start,
        end=end,
        ledger=ledger_df,
        summary=summary,
        hit_distribution=hit_distribution,
        calibration=calibration,
        logloss=logloss,
    )


def rolling_hit_rate(ledger: pd.DataFrame, window: int = 100) -> pd.DataFrame:
    """各策略的滚动平均命中数与累计收益，用于展示"优势是否稳定"。"""
    frames = []
    for name, group in ledger.groupby("strategy", sort=False):
        group = group.sort_values("t")
        frames.append(
            pd.DataFrame(
                {
                    "t": group["t"].to_numpy(),
                    "strategy": name,
                    "rolling_hits": group["front_hits"].rolling(window, min_periods=window // 2).mean().to_numpy(),
                    "cum_payout": group["payout"].cumsum().to_numpy(),
                    "cum_cost": group["cost"].cumsum().to_numpy(),
                }
            )
        )
    return pd.concat(frames, ignore_index=True)
