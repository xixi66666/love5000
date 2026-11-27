"""严格回测：只用历史信息选号，逐期结算真实奖级与奖金。

评价分两层：
* 结果层：命中个数、奖级分布、投入产出比（与理论超几何/期望值对比）；
* 概率层：对数损失、Brier 分数、校准曲线——比"中没中"灵敏得多，
  因为对数损失会惩罚过度自信的错误概率。

公开面：:class:`BacktestResult`（一次回测的全部产出）、:func:`run_backtest`（主入口）、
:func:`rolling_hit_rate`（滚动命中与累计收益）。

口径与单位：
    * ``mean_front_hits``：平均前区命中个数（个/注），理论值为 k²/N；
    * ``t_stat``：``(实测均值 − 理论值) / 标准误``，零假设是“与随机无差异”；
    * ``any_prize_rate``：至少中一个奖级的比例（0–1），与理论中奖率对照；
    * ``roi``：``奖金/投入 − 1``，受是否命中一二等奖的极端影响，只看它会误判策略；
    * ``mean_logloss``：每注前区概率的负对数似然（nats），均匀基准为 k·ln N；
    * ``lift``：``均匀基准 − 模型对数损失``，大于 0 才说明模型比随机更有预测力；
    * ``brier``：逐号码预测概率与 0/1 结果的均方误差。

“概率层”比“结果层”灵敏：一次回测里一二等奖几乎必然缺席，收益率由一两注中小奖主导，
方差远大于信号；而对数损失每一期都在提供信息。

边界：回测只能说明“这些策略在历史上没有跑赢随机”，不能反推未来。任何策略的正收益率
都来自奖金结构的厚尾与抽样噪声，不构成中奖保证，也不构成购彩建议。
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
    """一次回测的全部产出（逐期明细 + 各策略汇总 + 概率层指标）。

    Attributes:
        game: 彩种 key。
        start / end: 回测区间，左闭右开，实际回测 ``end - start`` 期。
        ledger: 逐期逐策略明细，列为 ``t`` / ``issue`` / ``date`` / ``strategy`` /
            ``front_hits`` / ``back_hits`` / ``tier`` / ``payout``（元）/ ``cost``（元）/
            ``front`` / ``back``（两位补零的号码文本）。
        summary: 按策略汇总，含平均命中、标准误、t 统计量、中奖率与投入产出。
        hit_distribution: 命中数分布长表，含 ``observed`` 与超几何 ``theory``。
        calibration: 概率分箱后的校准点，``predicted`` / ``observed`` / ``count``。
        logloss: 概率层指标，含逐期对数损失数组 ``per_draw``。
    """

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
    """逐期回测一组策略，并同时给出结果层与概率层评价。

    Args:
        data: 完整开奖数据。
        features: 逐期特征表（透传给 :func:`lottery.models.build_context`）。
        strategies: 待比较的策略实例；同一实例会在整个区间上复用。
        start: 起始期下标（0 起、含），调用方通常取最后 1500 期。
        end: 结束期下标（不含），默认到数据末尾；超过 ``data.n`` 会被截断。
        seed: 随机种子，固定它才能复现“随机基准”与并列打散的抽样结果。

    Returns:
        :class:`BacktestResult`；``ledger`` 的行数等于 ``(end - start) × len(strategies)``。

    Raises:
        KeyError: ``prize_amounts`` 缺少某期奖级金额（``data/*.csv`` 与 ``*_prizes.csv``
            不一致时会触发）；或 ``start >= end`` 使汇总表为空、随后按列名排序失败。

    实现要点：所有策略共用一个 ``rng``，因此策略顺序会影响各自抽到的票面；
    各策略的 ``score`` 只读 :class:`~lottery.models.Context` 里第 t 期之前的累计量，
    不存在未来信息泄漏。
    """
    game: Game = data.game
    end = data.n if end is None else min(end, data.n)
    ctx = build_context(data, features)
    amounts = prize_amounts(game.key)
    issues = data.df["issue"].to_numpy()
    tier_fn = PRIZE_TIER[game.key]
    rng = np.random.default_rng(seed)

    # 预先转成 set：结算要做 (end-start)×策略数 次交集，避免每次都做线性查找。
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
    # 及格线：随机一注的期望命中个数 k²/N；策略均值必须显著超过它才有研究价值。
    theoretical_hits = game.front_mean_hits
    rows = []
    for name, group in ledger_df.groupby("strategy", sort=False):
        hits = group["front_hits"].to_numpy(dtype=float)
        n = len(hits)
        mean = hits.mean()
        # 样本标准误；只有 1 期时无法估计离散度，置 NaN 而不是抛错。
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
    # 按平均命中降序：报告与图表都取 iloc[0] 当作“最佳策略”，因此这里的排序
    # 就是“最佳”的定义（而不是收益率）。
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
    # 均匀分布的每注对数损失 = k·ln N，是所有“预测力”判断的基准线。
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
            # 重新归一化并截断：防止某些策略的概率和为 0 或某号码概率为 0 时 log(0)。
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
        # 按预测概率的十分位分箱；unique 去掉重复分位点（大量并列概率时必然出现）。
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
    """各策略的滚动平均命中数与累计收益，用于展示"优势是否稳定"。

    Args:
        ledger: :attr:`BacktestResult.ledger`。
        window: 滚动窗口期数；前 ``window//2`` 期没有完整窗口，用 ``min_periods`` 放宽，
            避免曲线左端出现一长段空白。

    Returns:
        长表，列为 ``t`` / ``strategy`` / ``rolling_hits``（个/注）/ ``cum_payout``（元）/
        ``cum_cost``（元）；每个策略一段，段内按 ``t`` 升序。
    """
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
