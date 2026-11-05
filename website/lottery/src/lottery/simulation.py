"""决策层模拟：期望值、中奖等待时间、覆盖设计与蒙特卡洛资金曲线。

这一层回答的不是"下期开什么"，而是"这件事在数学上值不值得做、
用多少钱做、能买到多少确定性"。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .combinatorics import expected_payout, tier_probabilities
from .config import Game
from .data import LotteryData, prize_amounts, total_prize_payout


def rtp_series(data: LotteryData) -> pd.DataFrame:
    """逐期返奖率：官方派奖总额 / 当期销售额。"""
    payout = total_prize_payout(data.game.key)
    df = data.df.set_index("issue")
    frame = pd.DataFrame(
        {
            "date": df["date"],
            "sales": df["sales"].astype(float),
            "payout": payout.reindex(df.index).astype(float),
        }
    )
    frame["rtp"] = frame["payout"] / frame["sales"]
    frame = frame[(frame["sales"] > 0) & frame["rtp"].between(0, 3)]
    return frame.reset_index()


def ev_frame(data: LotteryData) -> pd.DataFrame:
    """逐期单注期望回报（元）与返奖率。"""
    game = data.game
    amounts = prize_amounts(game.key)
    tiers = tier_probabilities(game)
    rows = []
    for issue, row in amounts.iterrows():
        ev = float(sum(tiers[t] * row[t] for t in row.index))
        rows.append({"issue": issue, "ev": ev, "rtp": ev / game.price})
    frame = pd.DataFrame(rows)
    frame["date"] = data.df.set_index("issue")["date"].reindex(frame["issue"]).to_numpy()
    return frame


def ev_curve(game: Game) -> pd.DataFrame:
    """一等奖奖金从 0 到 3000 万时，单注期望回报的变化。"""
    tiers = tier_probabilities(game)
    fixed = sum(tiers[t] * amount for t, amount in _fixed_prizes(game).items())
    second = 150_000.0 if game.key == "ssq" else 150_000.0
    jackpots = np.linspace(0, 30_000_000, 301)
    ev = fixed + tiers[1] * jackpots + tiers[2] * second
    return pd.DataFrame({"jackpot": jackpots, "ev": ev, "rtp": ev / game.price})


def _fixed_prizes(game: Game) -> dict[int, float]:
    from .config import FIXED_PRIZES

    return FIXED_PRIZES[game.key]


def waiting_time(game: Game, draws: int = 4000) -> pd.DataFrame:
    """从今天起连续买，到首次中头奖所需期数的生存曲线。"""
    p = game.jackpot_odds
    n = np.arange(0, draws + 1)
    survival = (1 - p) ** n
    return pd.DataFrame(
        {
            "draws": n,
            "years": n / 150.0,
            "survival": survival,
            "cum_prob": 1 - survival,
            "spend": n * game.price,
        }
    )


def coverage(game: Game) -> pd.DataFrame:
    """买 m 注不同号码时，中头奖的概率与成本。"""
    m = np.unique(np.round(np.logspace(0, 7, 120)).astype(int))
    p = 1 - (1 - game.jackpot_odds) ** m
    return pd.DataFrame({"tickets": m, "cost": m * game.price, "prob": p})


def system_bet_table(game: Game, max_front: int = 12, max_back: int = 4) -> pd.DataFrame:
    """复式投注：前区选 a 个、后区选 b 个时的注数与金额。"""
    from math import comb

    rows = []
    for a in range(game.front_pick, max_front + 1):
        for b in range(game.back_pick, max_back + 1):
            tickets = comb(a, game.front_pick) * comb(b, game.back_pick)
            rows.append(
                {
                    "front_picked": a,
                    "back_picked": b,
                    "tickets": tickets,
                    "cost": tickets * game.price,
                    "jackpot_prob": tickets * game.jackpot_odds,
                }
            )
    return pd.DataFrame(rows)


def monte_carlo_bankroll(
    data: LotteryData,
    draws: int = 1500,
    simulations: int = 4000,
    seed: int = 20261104,
) -> dict:
    """模拟"每期买 1 注、连续买 draws 期"的收益分布。

    奖金金额从历史真实奖级金额中重抽样，奖级按理论概率抽样，
    因此同时保留了奖池波动和巨奖的厚尾特征。
    """
    game = data.game
    rng = np.random.default_rng(seed)
    amounts = prize_amounts(game.key).to_numpy(dtype=float)
    tiers = tier_probabilities(game)
    probs = tiers / tiers.sum()

    hist_index = rng.integers(0, amounts.shape[0], size=(simulations, draws))
    outcomes = rng.choice(len(probs), size=(simulations, draws), p=probs)
    payout = np.where(outcomes > 0, amounts[hist_index, np.maximum(outcomes - 1, 0)], 0.0)
    total = payout.sum(axis=1)
    cost = draws * game.price

    return {
        "total_payout": total,
        "cost": cost,
        "net": total - cost,
        "prob_profit": float((total > cost).mean()),
        "prob_any_jackpot": float((outcomes == 1).any(axis=1).mean()),
        "mean_payout": float(total.mean()),
        "median_payout": float(np.median(total)),
        "q90": float(np.quantile(total, 0.9)),
        "q99": float(np.quantile(total, 0.99)),
        "max_payout": float(total.max()),
        "rtp": float(total.mean() / cost),
    }


def bootstrap_ci(values: np.ndarray, n_boot: int = 4000, seed: int = 0) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    values = np.asarray(values, dtype=float)
    stats_ = rng.choice(values, size=(n_boot, len(values)), replace=True).mean(axis=1)
    return float(np.quantile(stats_, 0.025)), float(np.quantile(stats_, 0.975))
