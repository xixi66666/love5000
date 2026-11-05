"""彩种规则与概率常量。

所有规则参数集中在这里，任何一处修改都会同时影响：
数据加载 → 特征计算 → 理论分布 → 回测 → 图表。
"""

from __future__ import annotations

from dataclasses import dataclass
from math import comb


@dataclass(frozen=True)
class Game:
    """一个乐透型彩票的完整规则定义。"""

    key: str
    name: str
    front_label: str
    back_label: str
    front_pool: int
    front_pick: int
    back_pool: int
    back_pick: int
    price: float = 2.0
    # 一等奖单注封顶（元），用于期望值上界讨论
    first_prize_cap: int = 10_000_000
    # 追加投注：每注多付 1 元，一、二等奖追加部分为基本部分的 80%
    additional_price: float = 1.0

    @property
    def front_combinations(self) -> int:
        return comb(self.front_pool, self.front_pick)

    @property
    def back_combinations(self) -> int:
        return comb(self.back_pool, self.back_pick)

    @property
    def total_combinations(self) -> int:
        return self.front_combinations * self.back_combinations

    @property
    def jackpot_odds(self) -> float:
        return 1.0 / self.total_combinations

    @property
    def front_rate(self) -> float:
        """单个号码在任意一期前区/红球中出现的边际概率。"""
        return self.front_pick / self.front_pool

    @property
    def back_rate(self) -> float:
        return self.back_pick / self.back_pool

    @property
    def front_mean_hits(self) -> float:
        """随机一注在前区命中的期望个数 = k^2 / N。"""
        return self.front_pick**2 / self.front_pool

    @property
    def big_small_split(self) -> int:
        """大小分界：<= split 为小号（双色球 1-16 小，17-33 大）。"""
        return self.front_pool // 2

    @property
    def zone_edges(self) -> tuple[int, int]:
        """三区划分的两条边界。"""
        third = self.front_pool / 3
        return round(third), round(2 * third)


SSQ = Game(
    key="ssq",
    name="双色球",
    front_label="红球",
    back_label="蓝球",
    front_pool=33,
    front_pick=6,
    back_pool=16,
    back_pick=1,
    price=2.0,
    first_prize_cap=10_000_000,
)

DLT = Game(
    key="dlt",
    name="大乐透",
    front_label="前区",
    back_label="后区",
    front_pool=35,
    front_pick=5,
    back_pool=12,
    back_pick=2,
    price=2.0,
    first_prize_cap=10_000_000,
)

GAMES: dict[str, Game] = {g.key: g for g in (SSQ, DLT)}

# 奖级名称（用于把官方奖级表映射为 1..9 级）
CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def prize_tier_ssq(front_hits: int, back_hits: int) -> int:
    """双色球奖级：返回 1..6，未中奖返回 0。"""
    if front_hits == 6 and back_hits == 1:
        return 1
    if front_hits == 6 and back_hits == 0:
        return 2
    if front_hits == 5 and back_hits == 1:
        return 3
    if (front_hits == 5 and back_hits == 0) or (front_hits == 4 and back_hits == 1):
        return 4
    if (front_hits == 4 and back_hits == 0) or (front_hits == 3 and back_hits == 1):
        return 5
    if back_hits == 1 and front_hits <= 2:
        return 6
    return 0


def prize_tier_dlt(front_hits: int, back_hits: int) -> int:
    """大乐透奖级：返回 1..9，未中奖返回 0（不含追加）。"""
    table = {
        (5, 2): 1,
        (5, 1): 2,
        (5, 0): 3,
        (4, 2): 4,
        (4, 1): 5,
        (3, 2): 6,
        (4, 0): 7,
        (3, 1): 8,
        (2, 2): 8,
        (3, 0): 9,
        (2, 1): 9,
        (1, 2): 9,
        (0, 2): 9,
    }
    return table.get((front_hits, back_hits), 0)


PRIZE_TIER = {"ssq": prize_tier_ssq, "dlt": prize_tier_dlt}

# 固定奖金额（元）——用于期望值中不随奖池浮动的那部分
FIXED_PRIZES = {
    "ssq": {3: 3000.0, 4: 200.0, 5: 10.0, 6: 5.0},
    "dlt": {3: 10_000.0, 4: 3000.0, 5: 300.0, 6: 200.0, 7: 100.0, 8: 15.0, 9: 5.0},
}

# ---------------------------------------------------------------------------
# 大乐透 2026-02-02（第 26014 期）起的新规则：9 级合并为 7 级
#   3 等 = 5+0 或 4+2，4 等 = 4+1，5 等 = 4+0 或 3+2，6 等 = 3+1 或 2+2，7 等 = 其余后区中 2 个
# 该映射已用 112 期的中奖注数比例与理论概率逐一核对（误差 < 2%）。
# ---------------------------------------------------------------------------
DLT_2026_RULE_ISSUE = 26014

DLT_7_GROUPS: dict[int, tuple[tuple[int, int], ...]] = {
    1: ((5, 2),),
    2: ((5, 1),),
    3: ((5, 0), (4, 2)),
    4: ((4, 1),),
    5: ((4, 0), (3, 2)),
    6: ((3, 1), (2, 2)),
    7: ((3, 0), (2, 1), (1, 2), (0, 2)),
}

DLT_7_CONDITIONS = {
    1: "5 前 + 2 后",
    2: "5 前 + 1 后",
    3: "5+0 或 4+2",
    4: "4+1",
    5: "4+0 或 3+2",
    6: "3+1 或 2+2",
    7: "3+0 / 2+1 / 1+2 / 0+2",
}

# 单注奖金下限（元），实际为浮动但不会低于此值
DLT_7_MIN_PRIZE = {1: None, 2: None, 3: 5000.0, 4: 300.0, 5: 150.0, 6: 15.0, 7: 5.0}


def _dlt_prob(front_hits: int, back_hits: int) -> float:
    return (
        comb(5, front_hits) * comb(35 - 5, 5 - front_hits) / comb(35, 5)
        * comb(2, back_hits) * comb(12 - 2, 2 - back_hits) / comb(12, 2)
    )


def dlt_probabilities_7() -> list[float]:
    """7 级规则下各奖级的中奖概率，索引 0 未使用（长度 8）。"""
    out = [0.0] * 8
    for tier, groups in DLT_7_GROUPS.items():
        out[tier] = sum(_dlt_prob(*pair) for pair in groups)
    return out
