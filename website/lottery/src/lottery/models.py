"""候选模型（策略）。

七个策略覆盖了彩票圈最常见的几种"选号哲学"，外加一个纯随机基准：

1. random      均匀随机（理论上不可战胜的基准）
2. hot         热号：最近窗口出现次数最多
3. cold        冷号：当前遗漏最长
4. bayes       贝叶斯：Dirichlet–多项分布后验均值（全历史平滑频率）
5. markov      一阶马尔可夫：P(本期出现 | 上期出现)
6. trend       趋势：最近窗口出现率的线性斜率
7. balanced    形态均衡：在随机候选票中挑"最像典型开奖"的一张

热号给了 30 / 100 两个窗口，因此 :func:`default_strategies` 返回 8 个策略实例。

公开面：:class:`Context`（回测前的预计算）、:func:`build_context`、:class:`Strategy`
基类与 7 个子类、:func:`default_strategies`。

接口约定：``score()`` 返回值越大越优先；``probabilities()`` 返回 ``None`` 表示该策略
不提供概率预测（因而不参与对数损失与校准评估）；``pick_front()`` / ``pick_back()``
返回 1 起的升序号码数组。

时间边界：除 :class:`ColdStrategy` 在 ``t=0`` 的退化情形外，所有策略都只读取第 t 期
之前的累计量，回测不存在未来信息泄漏（真实回测起点远大于 0，不会触发该退化）。

结论边界：这些策略只是把常见的选号说法形式化，用来做对照实验。开奖是相互独立的
随机试验，任何 score / probabilities 都不含预测能力；回测里“优于随机”的结果
必须当成抽样噪声，而不是可复用的规律。
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
    """回测时预先计算好的累计量，避免每个策略重复扫描历史。

    所有数组的第 0 行/第 0 个元素都对应“还没有任何一期”的状态，
    因此 ``ctx.cum_front[t]`` 这类下标访问在语义上只包含第 t 期之前的信息
    （例外见模块文档）。

    Attributes:
        data: 完整开奖数据（只读）。
        features: :func:`lottery.features.draw_features` 的结果。
        cum_front / cum_back: ``(n+1, pool)`` 的累计出现次数，
            ``cum_front[t]`` 是前 t 期（下标 0..t-1）的出现次数。
        markov_num_front / markov_den_front / markov_num_back / markov_den_back:
            ``(n+1, pool)`` 的一阶转移分子/分母；``num[t]`` 是前 t 期里“上期出现且本期
            也出现”的次数，``den[t]`` 是前 t 期里“上期出现”的次数。
        omission_front / omission_back: ``(n, pool)`` 的遗漏序列，
            ``omission[t]`` 是第 t 期开奖后各号码的连续未出期数。
    """

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
        """彩种规则的快捷访问，等价于 ``self.data.game``。"""
        return self.data.game


def build_context(data: LotteryData, features: pd.DataFrame) -> Context:
    """把回测需要的全部历史累计量一次性算出来。

    Args:
        data: 完整开奖数据。
        features: 逐期特征表，仅透传给策略使用，本身不参与计算。

    Returns:
        填好全部累计量的 :class:`Context`；构造过程是 O(n·pool)，与回测期数无关。

    实现要点：``cumulative`` 在最前面补一行 0，使“窗口求和”退化成两次查表相减；
    ``markov`` 用前缀和累积 2×2 列联表，避免每个策略各自按号码重扫历史。
    """
    from .features import omission_series

    n = data.n
    front, back = data.front, data.back

    # 前缀和多补一行 0，让 _trailing 的窗口求和变成一次减法。
    def cumulative(matrix):
        """在矩阵前补一行 0 后做行方向累计和。

        Returns:
            ``(n+1, pool)`` 的 float64 矩阵，第 t 行是前 t 期的出现次数。
        """
        return np.vstack([np.zeros((1, matrix.shape[1])), np.cumsum(matrix, axis=0)]).astype(np.float64)

    # 一阶转移的前缀和：num[s+1] / den[s+1] 只统计到第 s 期为止的转移。
    def markov(matrix):
        """累积一阶转移的分子与分母。

        Returns:
            ``(num, den)``，都是 ``(n+1, pool)`` 的数组：``num[t]`` 是前 t 期里
            “上期出现且本期也出现”的次数，``den[t]`` 是前 t 期里“上期出现”的次数。
            最后一行的值直接复制自前一行，保证下标 n 也有定义。
        """
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
    """取累计矩阵在窗口 ``[t-window, t)`` 内的增量。

    Args:
        cum: :func:`build_context` 产出的 ``(n+1, pool)`` 累计矩阵。
        t: 当前期下标（不含第 t 期本身）。
        window: 窗口长度；``None`` 表示从第 0 期开始（全历史），
            窗口长于历史时自动截断到 0。

    Returns:
        长度 pool 的出现次数增量（单位：次）。
    """
    start = 0 if window is None else max(0, t - window)
    return cum[t] - cum[start]


class Strategy:
    """选号策略基类：把“score 越高越优先”的约定固化成统一接口。

    子类通常只需实现 :meth:`score`；想改变抽样方式（纯随机、整票形态匹配）的子类
    可以覆盖 :meth:`pick_front` / :meth:`pick_back`，想参与概率层评估
    （对数损失、校准）的子类则要实现 :meth:`probabilities`。
    """

    name = "base"
    # name 是回测结果、图表与报告里做关联的唯一键（例如 hot_30），必须全局唯一。
    label = "基准"
    window: int | None = None

    def score(self, ctx: Context, t: int, area: str) -> np.ndarray:
        """返回每个号码的得分（越大越优先），长度等于该区号码池大小。

        Args:
            ctx: 回测上下文。
            t: 当前期下标；实现只能读取 :class:`Context` 里第 t 期之前的累计量。
            area: ``"front"`` 或 ``"back"``。

        Raises:
            NotImplementedError: 基类不实现，子类必须覆盖。
        """
        raise NotImplementedError

    def probabilities(self, ctx: Context, t: int, area: str) -> np.ndarray | None:
        """返回每个号码的边缘出现概率（和为 1），或 ``None`` 表示不提供概率预测。"""
        return None

    # --- 通用选号 -------------------------------------------------------
    def pick_front(self, ctx: Context, t: int, rng: np.random.Generator) -> np.ndarray:
        """按 score 选出前区 ``front_pick`` 个号码，返回 1 起的升序数组。"""
        score = self.score(ctx, t, "front")
        return self._top_k(score, ctx.game.front_pick, rng)

    def pick_back(self, ctx: Context, t: int, rng: np.random.Generator) -> np.ndarray:
        """按 score 选出后区 ``back_pick`` 个号码，返回 1 起的升序数组。"""
        score = self.score(ctx, t, "back")
        return self._top_k(score, ctx.game.back_pick, rng)

    @staticmethod
    def _top_k(score: np.ndarray, k: int, rng: np.random.Generator) -> np.ndarray:
        """取 score 最高的 k 个号码。

        加 ``1e-9`` 量级的随机抖动再排序，一是打散并列分数（例如全历史计数相同的
        冷门号），二是让同一策略在不同随机种子下能给出不同但同样合法的票，
        避免结果被号码下标顺序绑架。
        """
        jitter = rng.random(len(score)) * 1e-9
        order = np.argsort(-(score + jitter))
        return np.sort(order[:k] + 1)


class RandomStrategy(Strategy):
    """均匀随机基准：理论上的“不可战胜线”，所有策略都应与它无法区分。

    覆盖了 ``pick_front`` / ``pick_back``，直接用 ``rng.choice`` 无放回抽样。
    其 ``score`` 恒返回前区长度的 0 向量；由于选号与概率预测都被覆盖，
    回测不会调用它去选后区，因此不需要按 ``area`` 区分长度。
    """

    name = "random"
    label = "随机基准"

    def score(self, ctx: Context, t: int, area: str) -> np.ndarray:
        """返回前区长度的全 0 向量（占位，本策略不按得分选号）。"""
        return np.zeros(ctx.data.front.shape[1])

    def probabilities(self, ctx: Context, t: int, area: str) -> np.ndarray:
        """均匀分布 ``1/pool``；这是对数损失与 Brier 分数的基准线。"""
        pool = ctx.game.front_pool if area == "front" else ctx.game.back_pool
        return np.full(pool, 1.0 / pool)

    def pick_front(self, ctx: Context, t: int, rng: np.random.Generator) -> np.ndarray:
        """从号码池无放回均匀抽 ``front_pick`` 个，返回 1 起的升序数组。"""
        return np.sort(rng.choice(ctx.game.front_pool, ctx.game.front_pick, replace=False) + 1)

    def pick_back(self, ctx: Context, t: int, rng: np.random.Generator) -> np.ndarray:
        """从后区池无放回均匀抽 ``back_pick`` 个，返回 1 起的升序数组。"""
        return np.sort(rng.choice(ctx.game.back_pool, ctx.game.back_pick, replace=False) + 1)


class HotStrategy(Strategy):
    """热号：最近窗口内出现次数最多的号码。

    这是“追热”派的代表，也是所有“走势图”类方法的原型。窗口越短越敏感，
    但窗口内的偏离本身来自抽样噪声，因此窗口长度只改变噪声的形态，不改变期望。
    """

    label = "热号"

    def __init__(self, window: int = 50):
        """窗口长度决定“热”的时间尺度；name 带上窗口后缀，便于回测结果区分。"""
        self.name = f"hot_{window}"
        self.window = window

    def _counts(self, ctx: Context, t: int, area: str) -> np.ndarray:
        """窗口内的出现次数（严格不含第 t 期），作为热号的得分。"""
        cum = ctx.cum_front if area == "front" else ctx.cum_back
        return _trailing(cum, t, self.window)

    def score(self, ctx: Context, t: int, area: str) -> np.ndarray:
        """热号得分就是窗口出现次数，单位“次”。"""
        return self._counts(ctx, t, area)

    def probabilities(self, ctx: Context, t: int, area: str) -> np.ndarray:
        """把窗口计数做拉普拉斯平滑（α=1）后变成概率，便于与其他策略比较对数损失。"""
        counts = self._counts(ctx, t, area)
        alpha = 1.0
        p = (counts + alpha) / (counts.sum() + alpha * len(counts))
        return p


class ColdStrategy(Strategy):
    """冷号：当前遗漏最长的号码（“该出了”派）。

    取的是 ``omission[t-1]``——第 t 期的遗漏要等开奖后才知道，选号必须用上一期结束时
    的状态。``t=0`` 时没有第 -1 期，代码退化为 ``omission[0]``（含当期结果）；
    真实回测起点远大于 0，不会触发，但单独调用时需要知道这个边界。
    """

    name = "cold"
    label = "冷号（遗漏最长）"

    def score(self, ctx: Context, t: int, area: str) -> np.ndarray:
        """遗漏期数越大越“冷”，因此直接拿遗漏值当得分（单位：期）。"""
        omission = ctx.omission_front if area == "front" else ctx.omission_back
        index = max(t - 1, 0)
        return omission[index]


class BayesStrategy(Strategy):
    """贝叶斯后验：Dirichlet–多项分布后验均值（全历史平滑频率）。

    均匀先验 ``Dir(α, …, α)`` 下，后验均值为 ``(c_i + α) / (n + αK)``；
    ``α`` 越大越把估计拉向 ``1/K``。它与“热号”的差别只是窗口长度与平滑方式，
    在独立随机开奖上的期望表现与随机基准一致。
    """

    name = "bayes"
    label = "贝叶斯后验"

    def __init__(self, prior: float = 1.0):
        """α 越大，后验频率越被拉向均匀分布 1/K。"""
        self.prior = prior

    def _counts(self, ctx: Context, t: int, area: str) -> np.ndarray:
        """全历史出现次数（截至第 t 期之前）。"""
        cum = ctx.cum_front if area == "front" else ctx.cum_back
        return cum[t]

    def score(self, ctx: Context, t: int, area: str) -> np.ndarray:
        """得分即后验概率，因此两者数值相同。"""
        return self.probabilities(ctx, t, area)

    def probabilities(self, ctx: Context, t: int, area: str) -> np.ndarray:
        """后验均值 ``(c_i + α) / (Σc + αK)``，结果和为 1。"""
        counts = self._counts(ctx, t, area)
        return (counts + self.prior) / (counts.sum() + self.prior * len(counts))


class MarkovStrategy(Strategy):
    """一阶马尔可夫：用 P(本期出现 | 上期出现) 排序。

    若各期独立，这个条件概率应等于边际概率，转移矩阵不提供任何信息；
    用它正是为了检验“上期开奖影响下期”这类说法。
    """

    name = "markov"
    label = "马尔可夫"

    def _rate(self, ctx: Context, t: int, area: str) -> np.ndarray:
        """带拉普拉斯平滑的转移概率 ``(num+1)/(den+2)``。

        ``+1`` / ``+2`` 相当于 Beta(1,1) 先验：分母为 0（该号码历史上从未在上期出现）
        时返回 0.5 而不是 0 或 NaN，保证排序稳定。
        """
        if area == "front":
            num, den = ctx.markov_num_front[t], ctx.markov_den_front[t]
        else:
            num, den = ctx.markov_num_back[t], ctx.markov_den_back[t]
        return (num + 1.0) / (den + 2.0)

    def score(self, ctx: Context, t: int, area: str) -> np.ndarray:
        """得分即平滑后的条件出现概率，单位无量纲。"""
        return self._rate(ctx, t, area)

    def probabilities(self, ctx: Context, t: int, area: str) -> np.ndarray:
        """把条件概率归一化成和为 1 的分布，作为“号码边缘概率”参与对数损失评估。"""
        p = self._rate(ctx, t, area)
        return p / p.sum()


class TrendStrategy(Strategy):
    """趋势：最近窗口内每个号码出现率的线性斜率。

    对每个号码单独做一元最小二乘，斜率大于 0 表示最近出现得越来越频繁。
    若开奖独立，斜率只是在拟合噪声；窗口内不足 10 期时直接返回全 0，
    避免用极短序列外推。
    """

    label = "趋势"

    def __init__(self, window: int = 200):
        """窗口长度决定斜率拟合的样本量；name 带上窗口后缀，便于回测结果区分。"""
        self.name = f"trend_{window}"
        self.window = window

    def score(self, ctx: Context, t: int, area: str) -> np.ndarray:
        """窗口内每号码出现率的 OLS 斜率（单位：次/期），越大越“走热”。"""
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

    这是对“号码要均衡、和值要居中”这类民间选号法的形式化：先随机生成
    ``candidates`` 张票，再按和值、奇数个数、跨度与各自理论均值的加权平方距离打分，
    取距离最小的一张。

    三个分母（15 / 1.2 / 8）是各特征的尺度常数，用来把三个量纲拉到可比范围，
    不是可调优的超参数；改它只改变“形态偏好”的强弱，不会改变中奖概率。
    """

    name = "balanced"
    label = "形态均衡"

    def __init__(self, candidates: int = 300):
        """候选票数越多越接近“理论众数”，代价是每期多做一次 N×pool 的随机矩阵。"""
        self.candidates = candidates

    def pick_front(self, ctx: Context, t: int, rng: np.random.Generator) -> np.ndarray:
        """在 ``candidates`` 张随机票里挑形态最接近理论众数的一张。

        目标值取精确组合分布的加权均值（而不是正态近似）；候选票用 ``rng.random``
        排序后取前 k 个，等价于每行做一次无放回均匀抽样，保证票内不重复。
        """
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
        """本策略不按号码打分，返回全 0 占位（选号逻辑在 pick_front 里）。"""
        return np.zeros(ctx.game.front_pool if area == "front" else ctx.game.back_pool)

    def pick_back(self, ctx: Context, t: int, rng: np.random.Generator) -> np.ndarray:
        """后区仍用均匀随机：大乐透后区只有 2 个号，形态偏好没有意义。"""
        return np.sort(rng.choice(ctx.game.back_pool, ctx.game.back_pick, replace=False) + 1)


def default_strategies() -> list[Strategy]:
    """回测用的 8 个策略：随机基准 + 6 类“选号哲学”（热号给两个窗口）。

    Returns:
        新的策略实例列表。顺序即回测输出的分组顺序；策略本身不持有随机状态，
        随机性全部来自回测时传入的 ``rng``，因此可以跨彩种复用同一份列表。
    """
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
