"""决策层模拟：期望值、中奖等待时间、覆盖设计与蒙特卡洛资金曲线。

这一层回答的不是"下期开什么"，而是"这件事在数学上值不值得做、
用多少钱做、能买到多少确定性"。

公开面：:func:`rtp_series`（逐期返奖率）、:func:`ev_frame`（逐期期望回报）、
:func:`ev_curve`（期望随头奖变化的曲线）、:func:`waiting_time`（等待时间生存曲线）、
:func:`coverage`（买 m 注的覆盖率）、:func:`system_bet_table`（复式投注注数）、
:func:`monte_carlo_bankroll`（资金曲线模拟）、:func:`bootstrap_ci`（均值的自助置信区间）。

口径与单位：
    * 期望回报 ``ev``：元/注；``rtp = ev / 票价``，无量纲比例；
    * 等待时间：期数与年（按每年约 150 期折算），投入金额为元；
    * 覆盖率：``1 − (1 − p)^m``，其中 m 是互不重复的注数；
    * 蒙特卡洛：``total_payout`` / ``cost`` / ``net`` 均为元，概率为 0–1。

边界：所有结果都是负期望游戏内部的成本核算。即使 ``prob_profit`` 不为 0，
它描述的也只是少数模拟路径，不代表可持续盈利，更不构成购彩建议。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .combinatorics import expected_payout, tier_probabilities
from .config import Game
from .data import LotteryData, prize_amounts, total_prize_payout


def rtp_series(data: LotteryData) -> pd.DataFrame:
    """逐期返奖率：官方派奖总额 / 当期销售额。

    Returns:
        DataFrame，列为 ``issue`` / ``date`` / ``sales``（元）/ ``payout``（元）/
        ``rtp``（0–1 的比例）。已剔除销售额非正、或返奖率落在 [0, 3] 之外的异常期
        ——奖池一次性滚存会让个别期次的派奖额远超当期销售额。
    """
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
    """逐期单注期望回报（元）与返奖率。

    一、二等奖用当期官方单注奖金，固定奖级用常量，因此结果反映“在该期奖金结构下
    买一注值多少钱”，而不是长期平均值。

    Returns:
        DataFrame，列为 ``issue`` / ``ev``（元/注）/ ``rtp``（``ev/2``）/ ``date``；
        行序与 ``prize_amounts`` 的期号顺序一致。
    """
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
    """一等奖奖金从 0 到 3000 万时，单注期望回报的变化。

    只让头奖金额变化、其余奖级保持不变，因此这是一条“上限参照曲线”，
    用来回答“要多大的头奖，买一注才在数学上不亏”。

    Args:
        game: 彩种规则。

    Returns:
        DataFrame，301 行，列为 ``jackpot``（元）/ ``ev``（元/注）/ ``rtp``（比例）。

    注：二等奖在曲线里按 15 万元常数近似，两种游戏当前使用同一假设。
    """
    tiers = tier_probabilities(game)
    fixed = sum(tiers[t] * amount for t, amount in _fixed_prizes(game).items())
    second = 150_000.0 if game.key == "ssq" else 150_000.0
    jackpots = np.linspace(0, 30_000_000, 301)
    ev = fixed + tiers[1] * jackpots + tiers[2] * second
    return pd.DataFrame({"jackpot": jackpots, "ev": ev, "rtp": ev / game.price})


def _fixed_prizes(game: Game) -> dict[int, float]:
    """固定奖级金额表（元/注）；延迟导入避免模块级循环依赖。"""
    from .config import FIXED_PRIZES

    return FIXED_PRIZES[game.key]


def waiting_time(game: Game, draws: int = 4000) -> pd.DataFrame:
    """从今天起连续买，到首次中头奖所需期数的生存曲线。

    每期独立，因此首次中奖所需期数服从几何分布：``P(需要超过 n 期) = (1-p)^n``。

    Args:
        game: 彩种规则。
        draws: 曲线最长展示的期数，默认 4000（约 26 年）。

    Returns:
        DataFrame，列为 ``draws``（期）/ ``years``（按每年 150 期折算）/ ``survival``
        （到第 n 期仍未中奖的概率）/ ``cum_prob``（至少中一次的累计概率）/ ``spend``（元）。
    """
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
    """买 m 注不同号码时，中头奖的概率与成本。

    Args:
        game: 彩种规则。

    Returns:
        DataFrame，列为 ``tickets`` / ``cost``（元）/ ``prob``。注数在对数尺度上取
        120 个点并去重，覆盖 1 注到 1000 万注。

    这里假设 m 注互不重复，此时覆盖率严格等于 ``1 − (1 − p)^m``；
    重复投注只是线性浪费钱，不会线性提高覆盖率。
    """
    m = np.unique(np.round(np.logspace(0, 7, 120)).astype(int))
    p = 1 - (1 - game.jackpot_odds) ** m
    return pd.DataFrame({"tickets": m, "cost": m * game.price, "prob": p})


def system_bet_table(game: Game, max_front: int = 12, max_back: int = 4) -> pd.DataFrame:
    """复式投注：前区选 a 个、后区选 b 个时的注数与金额。

    Args:
        game: 彩种规则。
        max_front: 前区最多复选到几个（含）。
        max_back: 后区最多复选到几个（含）。

    Returns:
        DataFrame，列为 ``front_picked`` / ``back_picked`` / ``tickets`` /
        ``cost``（元）/ ``jackpot_prob``（0–1）。注数 = C(a, k₁)·C(b, k₂)；
        这些组合互不重复，因此头奖概率就是注数乘以单注概率。
    """
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

    Args:
        data: 已加载数据，用于提供历史奖级金额。
        draws: 每个模拟路径的期数（默认 1500，约 10 年）。
        simulations: 模拟路径数（默认 4000）。
        seed: 随机种子，保证结果可复现。

    Returns:
        dict，键为 ``total_payout``（每条路径的总奖金数组，元）、``cost``（总投入，元）、
        ``net``（总奖金减总投入）、``prob_profit``（总奖金超过成本的路径比例）、
        ``prob_any_jackpot``（至少中一次头奖的路径比例）、``mean_payout`` /
        ``median_payout`` / ``q90`` / ``q99`` / ``max_payout``（元）与
        ``rtp``（总奖金 / 总投入）。

    注意：中奖事件在期与期之间独立，因此模拟不需要复刻真实期序；它衡量的是
    “给定奖金分布，这笔预算的收益分布”，不是对下一期的预测。
    """
    game = data.game
    rng = np.random.default_rng(seed)
    amounts = prize_amounts(game.key).to_numpy(dtype=float)
    tiers = tier_probabilities(game)
    probs = tiers / tiers.sum()

    hist_index = rng.integers(0, amounts.shape[0], size=(simulations, draws))
    outcomes = rng.choice(len(probs), size=(simulations, draws), p=probs)
    # outcomes 是奖级下标（0 表示未中奖，1..T 是奖级）；金额表列下标 = 奖级 − 1，
    # 因此先用 maximum 夹到合法列，未中奖的行随后会被 where 置 0。
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
    """用百分位自助法估计样本均值的 95% 置信区间。

    Args:
        values: 一维样本（例如逐期命中数或逐期返奖率）。
        n_boot: 重抽样次数。
        seed: 随机种子。

    Returns:
        ``(2.5% 分位, 97.5% 分位)``。自助分布是离散的，样本极小时区间可能退化成一个点。
    """
    rng = np.random.default_rng(seed)
    values = np.asarray(values, dtype=float)
    stats_ = rng.choice(values, size=(n_boot, len(values)), replace=True).mean(axis=1)
    return float(np.quantile(stats_, 0.025)), float(np.quantile(stats_, 0.975))
