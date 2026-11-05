"""候选模型（策略）。

七个策略覆盖了彩票圈最常见的几种"选号哲学"，外加一个纯随机基准：

1. random      均匀随机（理论上不可战胜的基准）
2. hot         热号：最近窗口出现次数最多
3. cold        冷号：当前遗漏最长
4. bayes       贝叶斯：Dirichlet–多项分布后验均值（全历史平滑频率）
5. markov      一阶马尔可夫：P(本期出现 | 上期出现)
6. trend       趋势：最近窗口出现率的线性斜率
7. balanced    形态均衡：在随机候选票中挑"最像典型开奖"的一张

所有策略都只使用第 t 期之前的数据，回测时不存在未来信息泄漏。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .combinatorics import feature_table
from .config import Game
from .data import LotteryData


@dataclass
class Context:
    """回测时预先计算好的累计量，避免每个策略重复扫描历史。"""

    data: LotteryData
    features: pd.DataFrame
    cum_front: np.ndarray
    cum_back: np.ndarray
    markov_num_front: np.ndarray
    markov_den_front: np.ndarray
    markov_num_back: np.ndarray
    markov_den_back: np.ndarray
    omission_front: np.ndarray
    omission_back: np.ndarray

    @property
    def game(self) -> Game:
        return self.data.game


def build_context(data: LotteryData, features: pd.DataFrame) -> Context:
    from .features import omission_series

    n = data.n
    front, back = data.front, data.back

    def cumulative(matrix):
        return np.vstack([np.zeros((1, matrix.shape[1])), np.cumsum(matrix, axis=0)]).astype(np.float64)

    def markov(matrix):
        num = np.zeros((n + 1, matrix.shape[1]))
        den = np.zeros((n + 1, matrix.shape[1]))
        for s in range(1, n):
            prev = matrix[s - 1].astype(bool)
            curr = matrix[s].astype(bool)
            num[s + 1] = num[s] + (prev & curr)
            den[s + 1] = den[s] + prev
        if n:
            num[n] = num[n - 1] + 0
            den[n] = den[n - 1] + 0
        return num, den

    num_f, den_f = markov(front)
    num_b, den_b = markov(back)
    return Context(
        data=data,
        features=features,
        cum_front=cumulative(front),
        cum_back=cumulative(back),
        markov_num_front=num_f,
        markov_den_front=den_f,
        markov_num_back=num_b,
        markov_den_back=den_b,
        omission_front=omission_series(front).astype(np.float64),
        omission_back=omission_series(back).astype(np.float64),
    )


def _trailing(cum: np.ndarray, t: int, window: int | None) -> np.ndarray:
    start = 0 if window is None else max(0, t - window)
    return cum[t] - cum[start]


class Strategy:
    name = "base"
    label = "基准"
    window: int | None = None

    def score(self, ctx: Context, t: int, area: str) -> np.ndarray:
        raise NotImplementedError

    def probabilities(self, ctx: Context, t: int, area: str) -> np.ndarray | None:
        return None

    # --- 通用选号 -------------------------------------------------------
    def pick_front(self, ctx: Context, t: int, rng: np.random.Generator) -> np.ndarray:
        score = self.score(ctx, t, "front")
        return self._top_k(score, ctx.game.front_pick, rng)

    def pick_back(self, ctx: Context, t: int, rng: np.random.Generator) -> np.ndarray:
        score = self.score(ctx, t, "back")
        return self._top_k(score, ctx.game.back_pick, rng)

    @staticmethod
    def _top_k(score: np.ndarray, k: int, rng: np.random.Generator) -> np.ndarray:
        jitter = rng.random(len(score)) * 1e-9
        order = np.argsort(-(score + jitter))
        return np.sort(order[:k] + 1)


class RandomStrategy(Strategy):
    name = "random"
    label = "随机基准"

    def score(self, ctx: Context, t: int, area: str) -> np.ndarray:
        return np.zeros(ctx.data.front.shape[1])

    def probabilities(self, ctx: Context, t: int, area: str) -> np.ndarray:
        pool = ctx.game.front_pool if area == "front" else ctx.game.back_pool
        return np.full(pool, 1.0 / pool)

    def pick_front(self, ctx: Context, t: int, rng: np.random.Generator) -> np.ndarray:
        return np.sort(rng.choice(ctx.game.front_pool, ctx.game.front_pick, replace=False) + 1)

    def pick_back(self, ctx: Context, t: int, rng: np.random.Generator) -> np.ndarray:
        return np.sort(rng.choice(ctx.game.back_pool, ctx.game.back_pick, replace=False) + 1)


class HotStrategy(Strategy):
    label = "热号"

    def __init__(self, window: int = 50):
        self.name = f"hot_{window}"
        self.window = window

    def _counts(self, ctx: Context, t: int, area: str) -> np.ndarray:
        cum = ctx.cum_front if area == "front" else ctx.cum_back
        return _trailing(cum, t, self.window)

    def score(self, ctx: Context, t: int, area: str) -> np.ndarray:
        return self._counts(ctx, t, area)

    def probabilities(self, ctx: Context, t: int, area: str) -> np.ndarray:
        counts = self._counts(ctx, t, area)
        alpha = 1.0
        p = (counts + alpha) / (counts.sum() + alpha * len(counts))
        return p


class ColdStrategy(Strategy):
    name = "cold"
    label = "冷号（遗漏最长）"

    def score(self, ctx: Context, t: int, area: str) -> np.ndarray:
        omission = ctx.omission_front if area == "front" else ctx.omission_back
        index = max(t - 1, 0)
        return omission[index]


class BayesStrategy(Strategy):
    name = "bayes"
    label = "贝叶斯后验"

    def __init__(self, prior: float = 1.0):
        self.prior = prior

    def _counts(self, ctx: Context, t: int, area: str) -> np.ndarray:
        cum = ctx.cum_front if area == "front" else ctx.cum_back
        return cum[t]

    def score(self, ctx: Context, t: int, area: str) -> np.ndarray:
        return self.probabilities(ctx, t, area)

    def probabilities(self, ctx: Context, t: int, area: str) -> np.ndarray:
        counts = self._counts(ctx, t, area)
        return (counts + self.prior) / (counts.sum() + self.prior * len(counts))


class MarkovStrategy(Strategy):
    name = "markov"
    label = "马尔可夫"

    def _rate(self, ctx: Context, t: int, area: str) -> np.ndarray:
        if area == "front":
            num, den = ctx.markov_num_front[t], ctx.markov_den_front[t]
        else:
            num, den = ctx.markov_num_back[t], ctx.markov_den_back[t]
        return (num + 1.0) / (den + 2.0)

    def score(self, ctx: Context, t: int, area: str) -> np.ndarray:
        return self._rate(ctx, t, area)

    def probabilities(self, ctx: Context, t: int, area: str) -> np.ndarray:
        p = self._rate(ctx, t, area)
        return p / p.sum()


class TrendStrategy(Strategy):
    label = "趋势"

    def __init__(self, window: int = 200):
        self.name = f"trend_{window}"
        self.window = window

    def score(self, ctx: Context, t: int, area: str) -> np.ndarray:
        matrix = ctx.data.front if area == "front" else ctx.data.back
        start = max(0, t - self.window)
        block = matrix[start:t].astype(np.float64)
        if len(block) < 10:
            return np.zeros(matrix.shape[1])
        x = np.arange(len(block), dtype=np.float64)
        x -= x.mean()
        denom = np.dot(x, x)
        slopes = x @ (block - block.mean(axis=0)) / denom
        return slopes


class BalancedStrategy(Strategy):
    """在随机候选票中，挑形态最接近理论众数的一张。

    这是对"号码要均衡、和值要居中"这类民间选号法的形式化。
    """

    name = "balanced"
    label = "形态均衡"

    def __init__(self, candidates: int = 300):
        self.candidates = candidates

    def pick_front(self, ctx: Context, t: int, rng: np.random.Generator) -> np.ndarray:
        game = ctx.game
        table = feature_table(game)
        sum_values, sum_p = table.pmf("sum")
        odd_values, odd_p = table.pmf("odd")
        span_values, span_p = table.pmf("span")
        target_sum = float(np.average(sum_values, weights=sum_p))
        target_odd = float(np.average(odd_values, weights=odd_p))
        target_span = float(np.average(span_values, weights=span_p))
        candidates = np.argsort(
            rng.random((self.candidates, game.front_pool)), axis=1
        )[:, : game.front_pick] + 1
        candidates.sort(axis=1)
        sums = candidates.sum(axis=1)
        odds = (candidates % 2 == 1).sum(axis=1)
        spans = candidates[:, -1] - candidates[:, 0]
        cost = (
            ((sums - target_sum) / 15.0) ** 2
            + ((odds - target_odd) / 1.2) ** 2
            + ((spans - target_span) / 8.0) ** 2
        )
        return candidates[int(np.argmin(cost))]

    def score(self, ctx: Context, t: int, area: str) -> np.ndarray:
        return np.zeros(ctx.game.front_pool if area == "front" else ctx.game.back_pool)

    def pick_back(self, ctx: Context, t: int, rng: np.random.Generator) -> np.ndarray:
        return np.sort(rng.choice(ctx.game.back_pool, ctx.game.back_pick, replace=False) + 1)


def default_strategies() -> list[Strategy]:
    return [
        RandomStrategy(),
        HotStrategy(30),
        HotStrategy(100),
        ColdStrategy(),
        BayesStrategy(),
        MarkovStrategy(),
        TrendStrategy(200),
        BalancedStrategy(),
    ]
