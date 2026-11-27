"""彩种规则与概率常量。

所有规则参数集中在这里，任何一处修改都会同时影响：
数据加载 → 特征计算 → 理论分布 → 回测 → 图表。

本模块只描述“规则”，不含可调超参数：``front_pool`` / ``front_pick`` 之类的数字就是
彩票本身的定义，改动它们等于换了一款游戏，而不是调参。

公开面：
    * :class:`Game`：一个彩种的完整规则，并提供组合数、头奖概率、边际出现率等派生量；
    * :data:`SSQ` / :data:`DLT` / :data:`GAMES`：两个彩种实例与按 key 的索引；
    * :func:`prize_tier_ssq` / :func:`prize_tier_dlt` / :data:`PRIZE_TIER`：
      由命中个数映射奖级（1 起，0 表示未中奖）；
    * :data:`FIXED_PRIZES`、:data:`DLT_7_*`：固定奖金额与 2026 年起的大乐透 7 级新规；
    * :func:`dlt_probabilities_7`：新规下各奖级的中奖概率。

金额单位统一为人民币元，概率为 0–1 的无量纲比例。
"""

from __future__ import annotations

from dataclasses import dataclass
from math import comb


@dataclass(frozen=True)
class Game:
    """一个乐透型彩票的完整规则定义。

    前后区相互独立：先从 ``front_pool`` 个号码中不放回摇出 ``front_pick`` 个，
    再从另一口锅 ``back_pool`` 中摇出 ``back_pick`` 个，全部猜中即头奖。
    ``price`` / ``first_prize_cap`` / ``additional_price`` 的单位是元，其余字段是号码个数。

    ``frozen=True`` 让实例可哈希，因而可以直接作为 :func:`functools.lru_cache` 的缓存键。
    """

    key: str
    name: str
    front_label: str
    back_label: str
    front_pool: int
    front_pick: int
    back_pool: int
    back_pick: int
    price: float = 2.0
    # 一等奖单注封顶（元）；只用于讨论期望值的数学上界，实际派奖仍受奖池与浮动规则约束。
    first_prize_cap: int = 10_000_000
    # 追加投注：每注多付 1 元，一、二等奖追加部分为基本部分的 80%
    additional_price: float = 1.0

    @property
    def front_combinations(self) -> int:
        """前区组合数 C(front_pool, front_pick)，单位：种。"""
        return comb(self.front_pool, self.front_pick)

    @property
    def back_combinations(self) -> int:
        """后区组合数 C(back_pool, back_pick)，单位：种。"""
        return comb(self.back_pool, self.back_pick)

    @property
    def total_combinations(self) -> int:
        """单注覆盖的组合总数（前后区相乘）；所有组合等可能，因此它的倒数就是头奖概率。"""
        return self.front_combinations * self.back_combinations

    @property
    def jackpot_odds(self) -> float:
        """一等奖（头奖）概率 = 1 / total_combinations，无量纲；任何选号方式都改变不了它。"""
        return 1.0 / self.total_combinations

    @property
    def front_rate(self) -> float:
        """单个号码在任意一期前区/红球中出现的边际概率 = front_pick / front_pool。

        它同时是逐号二项检验、遗漏几何分布与“热号是否有意义”这三件事的公共参数。
        """
        return self.front_pick / self.front_pool

    @property
    def back_rate(self) -> float:
        """单个号码在任意一期后区/蓝球中出现的边际概率 = back_pick / back_pool。"""
        return self.back_pick / self.back_pool

    @property
    def front_mean_hits(self) -> float:
        """随机一注在前区命中的期望个数 = k²/N，单位：个/注。

        这是回测的及格线：任何策略的平均命中必须先显著超过它，才值得继续研究。
        """
        return self.front_pick**2 / self.front_pool

    @property
    def big_small_split(self) -> int:
        """大小分界：<= split 为小号（双色球 1-16 小、17-33 大；大乐透 1-17 小、18-35 大）。"""
        return self.front_pool // 2

    @property
    def zone_edges(self) -> tuple[int, int]:
        """三区划分的两条边界（闭区间右端）：<= e1 为一区，(e1, e2] 为二区，> e2 为三区。"""
        third = self.front_pool / 3
        return round(third), round(2 * third)


# 双色球：33 个红球选 6 个 + 16 个蓝球选 1 个，2 元/注，6 个奖级。
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

# 大乐透：35 个前区选 5 个 + 12 个后区选 2 个，2 元/注（可加 1 元追加），9 个奖级；
# 2026-02-02（第 26014 期）起合并为 7 个奖级，见下方 DLT_7_* 常量。
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

# 按彩种 key 索引，供 load()、图表与报告统一取用。
GAMES: dict[str, Game] = {g.key: g for g in (SSQ, DLT)}

# 奖级名称（用于把官方奖级表映射为 1..9 级）：官方文案是“一等奖”…“九等奖”，取首字查表。
CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def prize_tier_ssq(front_hits: int, back_hits: int) -> int:
    """双色球奖级：返回 1..6，未中奖返回 0。

    Args:
        front_hits: 红球命中个数，0–6。
        back_hits: 蓝球命中个数，0–1。

    Returns:
        奖级编号；0 表示未中奖。六等奖只要求蓝球命中且红球不超过 2 个，
        因此“中 5 元”的实际概率主要由蓝球（1/16）决定，而不是红球分析。
    """
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
    """大乐透奖级：返回 1..9，未中奖返回 0（不含追加）。

    这里是 2019–2026 年初的 9 级规则；2026-02-02 起官方合并为 7 级，
    新规的奖级分组与最低奖金见 :data:`DLT_7_GROUPS` 与 :func:`dlt_probabilities_7`。

    Args:
        front_hits: 前区命中个数，0–5。
        back_hits: 后区命中个数，0–2。

    Returns:
        奖级编号；0 表示未中奖。未命中的 ``(front_hits, back_hits)`` 组合一律返回 0。
    """
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


# key -> 奖级判定函数；期望值、回测与检验都从这里取规则，避免各处各写一份。
PRIZE_TIER = {"ssq": prize_tier_ssq, "dlt": prize_tier_dlt}

# 固定奖金额（元/注）——用于期望值中不随奖池浮动的那部分。
# 只列固定奖级：双色球三至六等奖、大乐透三至九等奖；一、二等奖是浮动的，
# 逐期从官方 CSV 的 p<n>_amount 列读取。
FIXED_PRIZES = {
    "ssq": {3: 3000.0, 4: 200.0, 5: 10.0, 6: 5.0},
    "dlt": {3: 10_000.0, 4: 3000.0, 5: 300.0, 6: 200.0, 7: 100.0, 8: 15.0, 9: 5.0},
}

# ---------------------------------------------------------------------------
# 大乐透 2026-02-02（第 26014 期）起的新规则：9 级合并为 7 级
#   3 等 = 5+0 或 4+2，4 等 = 4+1，5 等 = 4+0 或 3+2，6 等 = 3+1 或 2+2，7 等 = 其余后区中 2 个
# 该映射已用 112 期的中奖注数比例与理论概率逐一核对（误差 < 2%）。
# ---------------------------------------------------------------------------
# 大乐透 7 级新规的起始期号（第 26014 期，2026-02-02 开奖）。
DLT_2026_RULE_ISSUE = 26014

# 7 级规则下每一奖级包含的 (前区命中, 后区命中) 组合；同一奖级内的组合概率相加。
DLT_7_GROUPS: dict[int, tuple[tuple[int, int], ...]] = {
    1: ((5, 2),),
    2: ((5, 1),),
    3: ((5, 0), (4, 2)),
    4: ((4, 1),),
    5: ((4, 0), (3, 2)),
    6: ((3, 1), (2, 2)),
    7: ((3, 0), (2, 1), (1, 2), (0, 2)),
}

# 与 DLT_7_GROUPS 一一对应的中文中奖条件，供报告与操作台直接展示。
DLT_7_CONDITIONS = {
    1: "5 前 + 2 后",
    2: "5 前 + 1 后",
    3: "5+0 或 4+2",
    4: "4+1",
    5: "4+0 或 3+2",
    6: "3+1 或 2+2",
    7: "3+0 / 2+1 / 1+2 / 0+2",
}

# 单注奖金下限（元/注）：实际金额浮动但不会低于此值；一、二等奖没有固定下限，用 None 表示。
DLT_7_MIN_PRIZE = {1: None, 2: None, 3: 5000.0, 4: 300.0, 5: 150.0, 6: 15.0, 7: 5.0}


def _dlt_prob(front_hits: int, back_hits: int) -> float:
    """单注恰好命中指定前后区个数的概率：两个超几何分布相乘（前后区独立摇奖）。"""
    return (
        comb(5, front_hits) * comb(35 - 5, 5 - front_hits) / comb(35, 5)
        * comb(2, back_hits) * comb(12 - 2, 2 - back_hits) / comb(12, 2)
    )


def dlt_probabilities_7() -> list[float]:
    """7 级规则下各奖级的中奖概率，索引 0 未使用（长度 8）。

    Returns:
        长度 8 的列表，``out[t]`` 是第 t 等奖的单注中奖概率（0–1），``out[0]`` 恒为 0。
        各级概率之和即新规下的总中奖率，其余为未中奖。
    """
    out = [0.0] * 8
    for tier, groups in DLT_7_GROUPS.items():
        out[tier] = sum(_dlt_prob(*pair) for pair in groups)
    return out
